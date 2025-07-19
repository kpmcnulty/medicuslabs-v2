from fastapi import APIRouter, HTTPException, Depends
from typing import List, Optional, Dict, Any, Union
from datetime import datetime
import asyncpg
from pydantic import BaseModel, Field
import json
import time
from sqlalchemy.ext.asyncio import AsyncSession

from core.database import get_db, get_pg_connection
from core.config import settings
from models.schemas import SourceType

router = APIRouter(prefix="/api/search", tags=["search-by-type"])


class DataTypeSearchQuery(BaseModel):
    """Simplified search query for specific data types"""
    q: Optional[str] = Field(None, description="Search query text")
    
    # Disease filtering
    diseases: Optional[List[str]] = Field(None, description="Filter by disease names")
    
    # Dynamic metadata filters - MongoDB-style operators
    metadata: Optional[Dict[str, Any]] = Field(None, description="Dynamic metadata filters")
    
    # Column filters from table UI
    columnFilters: Optional[List[Dict[str, Any]]] = Field(None, description="Column-specific filters")
    
    # Search configuration
    search_type: str = Field("keyword", description="Search type: keyword, semantic, or hybrid")
    return_fields: Optional[List[str]] = Field(None, description="Specific metadata fields to return")
    
    # Pagination
    limit: int = Field(50, le=10000)  # Allow higher limits for export
    offset: int = Field(0, ge=0)
    
    # Sorting
    sort_by: Optional[str] = Field("relevance", description="Sort field")
    sort_order: str = Field("desc", description="Sort order: asc or desc")


class DataTypeSearchResult(BaseModel):
    """Search result for specific data type"""
    id: int
    title: str
    url: str
    source: str
    created_at: datetime
    relevance_score: float
    summary: Optional[str] = None
    content_snippet: Optional[str] = None
    diseases: List[str] = []
    last_updated: Optional[datetime] = None
    metadata: Dict[str, Any] = {}
    highlights: Optional[Dict[str, List[str]]] = None


class DataTypeSearchResponse(BaseModel):
    """Search response for specific data type"""
    results: List[DataTypeSearchResult]
    total: int
    limit: int
    offset: int
    query: Optional[str]
    execution_time_ms: int
    columns: Optional[List[Dict[str, Any]]] = None
    data_type: str


def build_metadata_conditions(metadata_filters: Dict[str, Any], param_count: int) -> tuple[str, list, int]:
    """Build SQL conditions for metadata filters - reused from unified search"""
    conditions = []
    params = []
    
    for field, value in metadata_filters.items():
        json_path = "->".join([f"'{part}'" for part in field.split(".")])
        base_path = f"metadata->{json_path}"
        
        if isinstance(value, dict) and any(k.startswith("$") for k in value.keys()):
            for op, op_value in value.items():
                if op == "$eq":
                    conditions.append(f"{base_path} = ${param_count}")
                    params.append(json.dumps(op_value) if not isinstance(op_value, (str, int, float, bool)) else op_value)
                    param_count += 1
                elif op == "$ne":
                    conditions.append(f"{base_path} != ${param_count}")
                    params.append(json.dumps(op_value) if not isinstance(op_value, (str, int, float, bool)) else op_value)
                    param_count += 1
                elif op == "$in":
                    conditions.append(f"{base_path} = ANY(${param_count})")
                    params.append(op_value)
                    param_count += 1
                elif op == "$nin":
                    conditions.append(f"NOT ({base_path} = ANY(${param_count}))")
                    params.append(op_value)
                    param_count += 1
                elif op == "$contains":
                    if isinstance(op_value, list):
                        conditions.append(f"{base_path} @> ${param_count}::jsonb")
                        params.append(json.dumps(op_value))
                        param_count += 1
                    else:
                        conditions.append(f"{base_path} @> ${param_count}::jsonb")
                        params.append(json.dumps([op_value]))
                        param_count += 1
                elif op == "$exists":
                    if op_value:
                        conditions.append(f"{base_path} IS NOT NULL")
                    else:
                        conditions.append(f"{base_path} IS NULL")
                elif op in ["$gt", "$gte", "$lt", "$lte"]:
                    sql_op = {"$gt": ">", "$gte": ">=", "$lt": "<", "$lte": "<="}[op]
                    if isinstance(op_value, str) and "T" in op_value:
                        conditions.append(f"({base_path})::timestamp {sql_op} ${param_count}::timestamp")
                    else:
                        conditions.append(f"({base_path})::numeric {sql_op} ${param_count}::numeric")
                    params.append(op_value)
                    param_count += 1
                elif op == "$regex":
                    conditions.append(f"{base_path}::text ~* ${param_count}")
                    params.append(op_value)
                    param_count += 1
        else:
            conditions.append(f"{base_path} = ${param_count}")
            params.append(json.dumps(value) if not isinstance(value, (str, int, float, bool)) else value)
            param_count += 1
    
    return " AND ".join(conditions), params, param_count


async def build_data_type_query(query: DataTypeSearchQuery, source_category: str) -> tuple[str, list]:
    """Build optimized query for specific data type"""
    
    sql = """
        WITH search_results AS (
            SELECT DISTINCT 
                d.id,
                d.title,
                d.url,
                d.summary,
                d.content,
                d.created_at,
                d.doc_metadata as metadata,
                s.name as source_name,
                ARRAY(
                    SELECT dis.name 
                    FROM document_diseases dd 
                    JOIN diseases dis ON dd.disease_id = dis.id 
                    WHERE dd.document_id = d.id
                ) as disease_names
    """
    
    # Add relevance score if text search
    if query.q:
        sql += """,
                ts_rank(
                    to_tsvector('english', COALESCE(d.content, '') || ' ' || COALESCE(d.title, '')), 
                    plainto_tsquery('english', $1)
                ) as rank
        """
    else:
        sql += ", 1.0 as rank"
    
    sql += """
            FROM documents d
            JOIN sources s ON d.source_id = s.id
            WHERE s.category = $1
    """
    
    params = [source_category]
    param_count = 2
    
    # Text search
    if query.q:
        sql += f" AND to_tsvector('english', COALESCE(d.content, '') || ' ' || COALESCE(d.title, '')) @@ plainto_tsquery('english', ${param_count})"
        params.append(query.q)
        param_count += 1
    
    # Disease filter
    if query.diseases:
        sql += f""" AND EXISTS (
            SELECT 1 FROM document_diseases dd
            JOIN diseases dis ON dd.disease_id = dis.id
            WHERE dd.document_id = d.id
            AND dis.name = ANY(${param_count})
        )"""
        params.append(query.diseases)
        param_count += 1
    
    # Metadata filters
    if query.metadata:
        metadata_sql, metadata_params, param_count = build_metadata_conditions(
            query.metadata, param_count
        )
        if metadata_sql:
            sql += f" AND {metadata_sql}"
            params.extend(metadata_params)
    
    # Handle column filters
    if query.columnFilters:
        for filter_item in query.columnFilters:
            if 'id' in filter_item and 'value' in filter_item:
                column_id = filter_item['id']
                filter_value = filter_item['value']
                
                if isinstance(filter_value, str) and filter_value.strip():
                    # Simple text filter for now
                    if column_id == 'title':
                        sql += f" AND d.title ILIKE ${param_count}"
                        params.append(f'%{filter_value}%')
                        param_count += 1
                    elif column_id == 'source':
                        sql += f" AND s.name ILIKE ${param_count}"
                        params.append(f'%{filter_value}%')
                        param_count += 1
                    elif column_id.startswith('metadata.'):
                        field_name = column_id.replace('metadata.', '')
                        sql += f" AND d.metadata->>'{field_name}' ILIKE ${param_count}"
                        params.append(f'%{filter_value}%')
                        param_count += 1
    
    sql += ")"  # Close CTE
    
    # Main select
    sql += " SELECT * FROM search_results"
    
    # Data-type specific sorting
    if query.sort_by == "relevance" and query.q:
        sql += " ORDER BY rank DESC, created_at DESC"
    elif query.sort_by == "date" or query.sort_by == "last_updated":
        # Simplified data-type specific date sorting
        if source_category == 'publications':
            sql += f""" ORDER BY 
                COALESCE(
                    CASE WHEN metadata->>'publication_date' IS NOT NULL 
                        THEN (metadata->>'publication_date')::timestamp END,
                    created_at
                ) {query.sort_order.upper()}"""
        elif source_category == 'trials':
            sql += f""" ORDER BY 
                COALESCE(
                    CASE WHEN metadata->>'last_update' IS NOT NULL 
                        THEN (metadata->>'last_update')::timestamp END,
                    CASE WHEN metadata->>'start_date' IS NOT NULL 
                        THEN (metadata->>'start_date')::timestamp END,
                    created_at
                ) {query.sort_order.upper()}"""
        elif source_category == 'community':
            sql += f""" ORDER BY 
                COALESCE(
                    CASE WHEN metadata->>'created_date' IS NOT NULL 
                        THEN (metadata->>'created_date')::timestamp END,
                    created_at
                ) {query.sort_order.upper()}"""
        elif source_category == 'faers':
            sql += f""" ORDER BY 
                COALESCE(
                    CASE WHEN metadata->>'receive_date' IS NOT NULL 
                        THEN (metadata->>'receive_date')::timestamp END,
                    created_at
                ) {query.sort_order.upper()}"""
        else:
            sql += f" ORDER BY created_at {query.sort_order.upper()}"
    elif query.sort_by and "." in query.sort_by:
        # Sort by metadata field
        json_path = "->".join([f"'{part}'" for part in query.sort_by.split(".")])
        sql += f" ORDER BY metadata->{json_path} {query.sort_order.upper()}"
    else:
        sql += " ORDER BY created_at DESC"
    
    # Pagination
    sql += f" LIMIT ${param_count} OFFSET ${param_count + 1}"
    params.extend([query.limit, query.offset])
    
    return sql, params


def generate_data_type_columns(results: List[DataTypeSearchResult], data_type: str) -> List[Dict[str, Any]]:
    """Generate optimized columns for specific data type"""
    
    # Base columns for all types
    base_columns = [
        {"key": "title", "label": "Title", "sortable": True, "width": "300", "frozen": True},
        {"key": "source", "label": "Source", "sortable": True, "width": "150"},
    ]
    
    # Data-type specific base columns
    if data_type == 'publications':
        base_columns.extend([
            {"key": "metadata.authors", "label": "Authors", "sortable": False, "width": "200", "render": "list"},
            {"key": "metadata.journal", "label": "Journal", "sortable": False, "width": "180"},
            {"key": "metadata.publication_date", "label": "Published", "sortable": True, "width": "120", "render": "date"},
            {"key": "metadata.pmid", "label": "PMID", "sortable": False, "width": "100", "render": "link"},
        ])
    elif data_type == 'trials':
        base_columns.extend([
            {"key": "metadata.phase", "label": "Phase", "sortable": False, "width": "100", "render": "badge"},
            {"key": "metadata.status", "label": "Status", "sortable": False, "width": "120", "render": "badge"},
            {"key": "metadata.enrollment", "label": "Enrollment", "sortable": False, "width": "100", "render": "number"},
            {"key": "metadata.sponsor", "label": "Sponsor", "sortable": False, "width": "180"},
            {"key": "metadata.start_date", "label": "Start Date", "sortable": True, "width": "120", "render": "date"},
        ])
    elif data_type == 'community':
        base_columns.extend([
            {"key": "metadata.author", "label": "Author", "sortable": False, "width": "150"},
            {"key": "metadata.subreddit", "label": "Community", "sortable": False, "width": "120", "render": "badge"},
            {"key": "metadata.score", "label": "Score", "sortable": False, "width": "80", "render": "number"},
            {"key": "metadata.created_date", "label": "Posted", "sortable": True, "width": "120", "render": "date"},
        ])
    elif data_type == 'faers':
        base_columns.extend([
            {"key": "metadata.product_name", "label": "Product", "sortable": False, "width": "180"},
            {"key": "metadata.reaction", "label": "Reaction", "sortable": False, "width": "200"},
            {"key": "metadata.outcome", "label": "Outcome", "sortable": False, "width": "120", "render": "badge"},
            {"key": "metadata.receive_date", "label": "Report Date", "sortable": True, "width": "120", "render": "date"},
        ])
    
    # Add dynamic metadata columns for fields not covered above
    if results:
        existing_fields = {col["key"].replace("metadata.", "") for col in base_columns if col["key"].startswith("metadata.")}
        
        # Analyze remaining metadata fields
        metadata_analysis = {}
        sample_size = min(20, len(results))
        
        for result in results[:sample_size]:
            for field_name, value in result.metadata.items():
                if field_name not in existing_fields and field_name not in metadata_analysis:
                    metadata_analysis[field_name] = {
                        "count": 0,
                        "types": set(),
                        "non_null_count": 0
                    }
                
                if field_name not in existing_fields:
                    field_info = metadata_analysis[field_name]
                    field_info["count"] += 1
                    
                    if value is not None:
                        field_info["non_null_count"] += 1
                        if isinstance(value, list):
                            field_info["types"].add("list")
                        elif isinstance(value, bool):
                            field_info["types"].add("boolean")
                        elif isinstance(value, (int, float)):
                            field_info["types"].add("number")
                        elif isinstance(value, str):
                            field_info["types"].add("string")
                            if any(pattern in value for pattern in ["-", "/", "T"]) and len(value) <= 30:
                                field_info["types"].add("date")
        
        # Add high-frequency metadata fields
        for field_name, field_info in metadata_analysis.items():
            if field_info["non_null_count"] >= sample_size * 0.3:  # 30% threshold
                col_config = {
                    "key": f"metadata.{field_name}",
                    "label": field_name.replace('_', ' ').title(),
                    "sortable": False,
                    "width": "150"
                }
                
                # Set render type
                types = field_info["types"]
                if "list" in types:
                    col_config["render"] = "list"
                    col_config["width"] = "200"
                elif "boolean" in types:
                    col_config["render"] = "boolean"
                    col_config["width"] = "80"
                elif "number" in types:
                    col_config["render"] = "number"
                    col_config["width"] = "100"
                elif "date" in types:
                    col_config["render"] = "date"
                    col_config["width"] = "120"
                
                base_columns.append(col_config)
    
    return base_columns


async def search_data_type(query: DataTypeSearchQuery, source_category: str, data_type_name: str):
    """Execute search for specific data type"""
    start_time = time.time()
    
    async with get_pg_connection() as conn:
        # Build and execute query
        sql, params = await build_data_type_query(query, source_category)
        results = await conn.fetch(sql, *params)
        
        # Get total count
        count_sql = sql.split("ORDER BY")[0].replace(
            "SELECT * FROM search_results",
            "SELECT COUNT(*) FROM search_results"
        )
        count_params = params[:-2] if len(params) >= 2 else params
        total_count = await conn.fetchval(count_sql, *count_params)
        
        # Process results
        search_results = []
        for row in results:
            metadata = json.loads(row['metadata']) if row['metadata'] else {}
            
            # Extract data-type specific last_updated
            last_updated = None
            if source_category == 'publications' and metadata.get('publication_date'):
                try:
                    last_updated = datetime.fromisoformat(metadata['publication_date'].replace('Z', '+00:00'))
                except:
                    pass
            elif source_category == 'trials' and metadata.get('last_update'):
                try:
                    last_updated = datetime.fromisoformat(metadata['last_update'].replace('Z', '+00:00'))
                except:
                    pass
            elif source_category == 'community' and metadata.get('created_date'):
                try:
                    last_updated = datetime.fromisoformat(metadata['created_date'].replace('Z', '+00:00'))
                except:
                    pass
            elif source_category == 'faers' and metadata.get('receive_date'):
                try:
                    last_updated = datetime.fromisoformat(metadata['receive_date'].replace('Z', '+00:00'))
                except:
                    pass
            
            if not last_updated:
                last_updated = row['created_at']
            
            result = DataTypeSearchResult(
                id=row['id'],
                title=row['title'] or 'Untitled',
                url=row['url'],
                source=row['source_name'],
                created_at=row['created_at'],
                relevance_score=float(row['rank']) if row.get('rank') else 1.0,
                summary=row['summary'],
                content_snippet=(row['content'][:200] + '...') if row['content'] else None,
                diseases=row['disease_names'] or [],
                metadata=metadata,
                last_updated=last_updated
            )
            
            search_results.append(result)
        
        execution_time = int((time.time() - start_time) * 1000)
        
        # Generate optimized columns
        columns = generate_data_type_columns(search_results, data_type_name)
        
        return DataTypeSearchResponse(
            results=search_results,
            total=total_count or 0,
            limit=query.limit,
            offset=query.offset,
            query=query.q,
            execution_time_ms=execution_time,
            columns=columns,
            data_type=data_type_name
        )


@router.post("/publications", response_model=DataTypeSearchResponse)
async def search_publications(query: DataTypeSearchQuery):
    """Search publications (PubMed, PMC, etc.)"""
    return await search_data_type(query, 'publications', 'publications')


@router.post("/trials", response_model=DataTypeSearchResponse)
async def search_trials(query: DataTypeSearchQuery):
    """Search clinical trials (ClinicalTrials.gov, etc.)"""
    return await search_data_type(query, 'trials', 'trials')


@router.post("/community", response_model=DataTypeSearchResponse)
async def search_community(query: DataTypeSearchQuery):
    """Search community posts (Reddit, HealthUnlocked, etc.)"""
    return await search_data_type(query, 'community', 'community')


@router.post("/faers", response_model=DataTypeSearchResponse)
async def search_faers(query: DataTypeSearchQuery):
    """Search FAERS adverse event reports"""
    return await search_data_type(query, 'safety', 'faers')