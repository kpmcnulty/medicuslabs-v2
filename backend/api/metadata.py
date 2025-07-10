from fastapi import APIRouter, HTTPException, Query
from typing import List, Dict, Any, Optional
import asyncpg
from pydantic import BaseModel
import json
from collections import defaultdict
from core.database import get_pg_connection
from models.schemas import SourceType

router = APIRouter(prefix="/api/metadata", tags=["metadata"])


class FieldInfo(BaseModel):
    """Information about a metadata field"""
    name: str
    type: str  # string, number, array, object, date
    display_name: str
    filterable: bool = True
    sortable: bool = True
    array_type: Optional[str] = None
    sample_values: List[Any] = []
    value_count: int = 0
    description: Optional[str] = None


class SourceSchema(BaseModel):
    """Schema information for a source"""
    source: str
    source_type: SourceType
    document_count: int
    core_fields: List[FieldInfo]
    metadata_fields: List[FieldInfo]


class MetadataValuesRequest(BaseModel):
    """Request for metadata values"""
    source_type: Optional[str] = None
    source_name: Optional[str] = None
    field: str
    disease_filter: Optional[str] = None
    search: Optional[str] = None
    limit: int = 100


class MetadataValue(BaseModel):
    """A metadata field value with count"""
    value: Any
    count: int
    display_value: Optional[str] = None


# Field display name mappings
FIELD_DISPLAY_NAMES = {
    # Clinical Trials fields
    'nct_id': 'NCT ID',
    'phase': 'Study Phase',
    'status': 'Status',
    'conditions': 'Conditions',
    'interventions': 'Interventions',
    'sponsors': 'Sponsors',
    'start_date': 'Start Date',
    'completion_date': 'Completion Date',
    'enrollment': 'Enrollment',
    'study_type': 'Study Type',
    'eligibility': 'Eligibility',
    'outcomes': 'Outcomes',
    'locations': 'Locations',
    
    # PubMed fields
    'pmid': 'PMID',
    'doi': 'DOI',
    'journal': 'Journal',
    'authors': 'Authors',
    'publication_date': 'Publication Date',
    'article_types': 'Article Types',
    'mesh_terms': 'MeSH Terms',
    'chemicals': 'Chemicals/Drugs',
    'keywords': 'Keywords',
    'grants': 'Grants',
    
    # Common fields
    'title': 'Title',
    'url': 'URL',
    'content': 'Content',
    'summary': 'Summary',
    'created_at': 'Added Date',
    'updated_at': 'Last Updated',
    'source': 'Source',
    'disease_tags': 'Disease Tags'
}

# Field descriptions
FIELD_DESCRIPTIONS = {
    'phase': 'Clinical trial phase (e.g., Phase 1, Phase 2, Phase 3)',
    'mesh_terms': 'Medical Subject Headings - standardized medical terminology',
    'chemicals': 'Chemical substances and drugs mentioned in the document',
    'nct_id': 'ClinicalTrials.gov identifier',
    'pmid': 'PubMed identifier',
    'doi': 'Digital Object Identifier'
}


async def analyze_field_type(conn: asyncpg.Connection, source_id: int, field_path: str) -> Dict[str, Any]:
    """Analyze the type and values of a metadata field"""
    # Check if it's a nested field
    if '.' in field_path:
        # Handle nested fields like outcomes.primary
        parts = field_path.split('.')
        base_query = f"SELECT jsonb_typeof(metadata->'{parts[0]}') as type FROM documents WHERE source_id = $1 AND metadata->'{parts[0]}' IS NOT NULL LIMIT 1"
    else:
        base_query = f"SELECT jsonb_typeof(metadata->'{field_path}') as type FROM documents WHERE source_id = $1 AND metadata->'{field_path}' IS NOT NULL LIMIT 1"
    
    type_result = await conn.fetchrow(base_query, source_id)
    field_type = type_result['type'] if type_result else 'string'
    
    # Get sample values
    sample_values = []
    value_count = 0
    
    if field_type == 'array':
        # For arrays, get unique elements
        if field_path in ['authors', 'chemicals', 'mesh_terms', 'conditions', 'keywords', 'article_types']:
            values_query = f"""
                SELECT DISTINCT jsonb_array_elements_text(metadata->'{field_path}') as value
                FROM documents
                WHERE source_id = $1 
                AND metadata->'{field_path}' IS NOT NULL
                AND jsonb_typeof(metadata->'{field_path}') = 'array'
                LIMIT 20
            """
            values = await conn.fetch(values_query, source_id)
            sample_values = [v['value'] for v in values if v['value']]
            
            # Get total count
            count_query = f"""
                SELECT COUNT(DISTINCT elem.value) as count
                FROM documents d,
                     jsonb_array_elements_text(d.metadata->'{field_path}') elem(value)
                WHERE d.source_id = $1
            """
            count_result = await conn.fetchrow(count_query, source_id)
            value_count = count_result['count'] if count_result else 0
            
    elif field_type in ['string', 'number']:
        # For simple types, get distinct values
        values_query = f"""
            SELECT DISTINCT metadata->>'{field_path}' as value, COUNT(*) as count
            FROM documents
            WHERE source_id = $1 
            AND metadata->>'{field_path}' IS NOT NULL
            GROUP BY metadata->>'{field_path}'
            ORDER BY count DESC
            LIMIT 20
        """
        values = await conn.fetch(values_query, source_id)
        sample_values = [v['value'] for v in values if v['value']]
        value_count = len(values)
    
    return {
        'type': field_type,
        'sample_values': sample_values[:10],  # Limit samples
        'value_count': value_count
    }


@router.get("/schema/{source_type}", response_model=SourceSchema)
async def get_source_schema(source_type: str):
    """Get the metadata schema for a specific source type"""
    
    async with get_pg_connection() as conn:
        # Map source type to actual source names
        source_mapping = {
            'publications': ['PubMed'],
            'trials': ['ClinicalTrials.gov'],
            'secondary': ['Reddit Medical', 'HealthUnlocked', 'Patient.info Forums'],
            'pubmed': ['PubMed'],
            'clinicaltrials': ['ClinicalTrials.gov']
        }
        
        source_names = source_mapping.get(source_type.lower(), [source_type])
        
        # Get source info
        source_query = """
            SELECT s.*, COUNT(d.id) as doc_count
            FROM sources s
            LEFT JOIN documents d ON s.id = d.source_id
            WHERE s.name = ANY($1)
            GROUP BY s.id
            LIMIT 1
        """
        
        source_info = await conn.fetchrow(source_query, source_names)
        if not source_info:
            raise HTTPException(status_code=404, detail=f"Source type '{source_type}' not found")
        
        # Core fields available for all documents
        core_fields = [
            FieldInfo(
                name="title",
                type="string",
                display_name="Title",
                sortable=True,
                filterable=True
            ),
            FieldInfo(
                name="url",
                type="string", 
                display_name="URL",
                sortable=False,
                filterable=False
            ),
            FieldInfo(
                name="summary",
                type="string",
                display_name="Summary",
                sortable=False,
                filterable=True
            ),
            FieldInfo(
                name="created_at",
                type="date",
                display_name="Added Date",
                sortable=True,
                filterable=True
            )
        ]
        
        # Get all unique metadata fields for this source
        metadata_query = """
            SELECT DISTINCT jsonb_object_keys(metadata) as field_name
            FROM documents
            WHERE source_id = $1
            AND metadata IS NOT NULL
        """
        
        metadata_fields = []
        field_results = await conn.fetch(metadata_query, source_info['id'])
        
        for row in field_results:
            field_name = row['field_name']
            
            # Analyze field type and values
            field_analysis = await analyze_field_type(conn, source_info['id'], field_name)
            
            # Determine if field should be filterable/sortable
            filterable = field_analysis['value_count'] < 1000  # Don't filter on high-cardinality fields
            sortable = field_analysis['type'] in ['string', 'number'] and field_analysis['value_count'] < 100
            
            metadata_fields.append(FieldInfo(
                name=f"metadata.{field_name}",
                type=field_analysis['type'],
                display_name=FIELD_DISPLAY_NAMES.get(field_name, field_name.replace('_', ' ').title()),
                filterable=filterable,
                sortable=sortable,
                sample_values=field_analysis['sample_values'],
                value_count=field_analysis['value_count'],
                description=FIELD_DESCRIPTIONS.get(field_name)
            ))
        
        # Sort metadata fields by display name
        metadata_fields.sort(key=lambda x: x.display_name)
        
        return SourceSchema(
            source=source_info['name'],
            source_type=source_info['type'],
            document_count=source_info['doc_count'],
            core_fields=core_fields,
            metadata_fields=metadata_fields
        )


@router.get("/schema", response_model=List[SourceSchema])
async def get_all_schemas():
    """Get metadata schemas for all active sources"""
    
    async with get_pg_connection() as conn:
        # Get all active sources
        sources_query = """
            SELECT s.*, COUNT(d.id) as doc_count
            FROM sources s
            LEFT JOIN documents d ON s.id = d.source_id
            WHERE s.is_active = true
            GROUP BY s.id
            HAVING COUNT(d.id) > 0
            ORDER BY s.type, s.name
        """
        
        sources = await conn.fetch(sources_query)
        schemas = []
        
        for source in sources:
            # Use the single source schema function
            schema = await get_source_schema(source['name'])
            schemas.append(schema)
        
        return schemas


@router.post("/values", response_model=List[MetadataValue])
async def get_metadata_values(request: MetadataValuesRequest):
    """Get unique values for a metadata field with counts"""
    
    async with get_pg_connection() as conn:
        # Build base query
        field_path = request.field.replace('metadata.', '') if request.field.startswith('metadata.') else request.field
        
        # Determine if this is an array field
        type_query = f"""
            SELECT DISTINCT jsonb_typeof(metadata->'{field_path}') as type
            FROM documents
            WHERE metadata->'{field_path}' IS NOT NULL
            LIMIT 1
        """
        
        type_result = await conn.fetchrow(type_query)
        is_array = type_result and type_result['type'] == 'array'
        
        # Build the values query
        if is_array:
            # Handle array fields
            base_query = f"""
                SELECT elem.value as value, COUNT(DISTINCT d.id) as count
                FROM documents d
                JOIN sources s ON d.source_id = s.id
                CROSS JOIN LATERAL jsonb_array_elements_text(d.metadata->'{field_path}') elem(value)
                WHERE d.metadata->'{field_path}' IS NOT NULL
            """
        else:
            # Handle scalar fields
            base_query = f"""
                SELECT d.metadata->>'{field_path}' as value, COUNT(*) as count
                FROM documents d
                JOIN sources s ON d.source_id = s.id
                WHERE d.metadata->>'{field_path}' IS NOT NULL
            """
        
        # Add filters
        conditions = []
        params = []
        param_counter = 1
        
        if request.source_type:
            conditions.append(f"s.type = ${param_counter}")
            params.append(request.source_type)
            param_counter += 1
        
        if request.source_name:
            conditions.append(f"s.name = ${param_counter}")
            params.append(request.source_name)
            param_counter += 1
        
        if request.disease_filter:
            conditions.append(f"""
                EXISTS (
                    SELECT 1 FROM document_diseases dd
                    JOIN diseases dis ON dd.disease_id = dis.id
                    WHERE dd.document_id = d.id
                    AND dis.name ILIKE ${param_counter}
                )
            """)
            params.append(f"%{request.disease_filter}%")
            param_counter += 1
        
        if conditions:
            base_query += " AND " + " AND ".join(conditions)
        
        # Add search filter if provided
        if request.search:
            if is_array:
                base_query += f" AND elem.value ILIKE ${param_counter}"
            else:
                base_query += f" AND d.metadata->>'{field_path}' ILIKE ${param_counter}"
            params.append(f"%{request.search}%")
            param_counter += 1
        
        # Group and order
        base_query += """
            GROUP BY value
            HAVING COUNT(*) > 0
            ORDER BY count DESC, value
            LIMIT $""" + str(param_counter)
        
        params.append(request.limit)
        
        # Execute query
        results = await conn.fetch(base_query, *params)
        
        # Format results
        values = []
        for row in results:
            if row['value']:  # Skip null values
                # Special formatting for certain fields
                display_value = row['value']
                
                if field_path == 'phase' and isinstance(row['value'], str):
                    # Clean up phase values
                    display_value = row['value'].replace('PHASE', 'Phase')
                elif field_path == 'status':
                    # Capitalize status
                    display_value = row['value'].title()
                
                values.append(MetadataValue(
                    value=row['value'],
                    count=row['count'],
                    display_value=display_value if display_value != row['value'] else None
                ))
        
        return values


@router.get("/field-correlations/{field}")
async def get_field_correlations(
    field: str,
    value: str,
    source_type: Optional[str] = None,
    limit: int = Query(10, le=50)
):
    """Get correlated field values for a given field/value pair"""
    
    async with get_pg_connection() as conn:
        field_path = field.replace('metadata.', '') if field.startswith('metadata.') else field
        
        # Find documents with this field/value
        docs_query = f"""
            SELECT d.id, d.metadata, s.name as source_name
            FROM documents d
            JOIN sources s ON d.source_id = s.id
            WHERE d.metadata->>'{field_path}' = $1
        """
        
        params = [value]
        if source_type:
            docs_query += " AND s.type = $2"
            params.append(source_type)
        
        docs = await conn.fetch(docs_query, *params)
        
        if not docs:
            return {"correlations": []}
        
        # Analyze other fields in these documents
        correlations = defaultdict(lambda: defaultdict(int))
        
        for doc in docs:
            if doc['metadata']:
                metadata = json.loads(doc['metadata'])
                for other_field, other_value in metadata.items():
                    if other_field != field_path:
                        if isinstance(other_value, list):
                            for item in other_value:
                                correlations[other_field][str(item)] += 1
                        elif other_value is not None:
                            correlations[other_field][str(other_value)] += 1
        
        # Format results
        correlation_results = []
        for corr_field, values in correlations.items():
            top_values = sorted(values.items(), key=lambda x: x[1], reverse=True)[:5]
            if top_values:
                correlation_results.append({
                    "field": corr_field,
                    "display_name": FIELD_DISPLAY_NAMES.get(corr_field, corr_field),
                    "top_values": [
                        {"value": v, "count": c} for v, c in top_values
                    ]
                })
        
        # Sort by total correlation strength
        correlation_results.sort(
            key=lambda x: sum(v["count"] for v in x["top_values"]),
            reverse=True
        )
        
        return {
            "field": field,
            "value": value,
            "document_count": len(docs),
            "correlations": correlation_results[:limit]
        }