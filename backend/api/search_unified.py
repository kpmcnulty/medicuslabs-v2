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

router = APIRouter(prefix="/api/search", tags=["search"])


class UnifiedSearchQuery(BaseModel):
    """Unified search with fully dynamic metadata support"""
    q: Optional[str] = Field(None, description="Search query text")
    
    # Source filtering
    sources: Optional[List[str]] = Field(None, description="Filter by source names")
    source_categories: Optional[List[str]] = Field(None, description="Filter by source categories (publications, trials, community)")
    
    # Disease filtering
    diseases: Optional[List[str]] = Field(None, description="Filter by disease names")
    
    # Dynamic metadata filters - completely flexible
    metadata: Optional[Dict[str, Any]] = Field(None, description="Dynamic metadata filters using MongoDB-style operators")
    
    # Search configuration
    search_type: str = Field("keyword", description="Search type: keyword, semantic, or hybrid")
    return_fields: Optional[List[str]] = Field(None, description="Specific fields to return from metadata")
    facets: Optional[List[str]] = Field(None, description="Fields to generate facet counts for")
    
    # Pagination
    limit: int = Field(50, le=100)
    offset: int = Field(0, ge=0)
    
    # Sorting
    sort_by: Optional[str] = Field("relevance", description="Sort field (relevance, date, or any metadata field)")
    sort_order: str = Field("desc", description="Sort order: asc or desc")


class FacetValue(BaseModel):
    """A facet value with count"""
    value: Any
    count: int
    label: Optional[str] = None


class SearchFacets(BaseModel):
    """Faceted search results"""
    field: str
    values: List[FacetValue]
    total_unique: int


class UnifiedSearchResult(BaseModel):
    """Unified search result with flexible metadata"""
    # Core fields always present
    id: int
    title: str
    url: str
    source: str
    source_category: Optional[str]
    created_at: datetime
    relevance_score: float
    
    # Optional core fields
    summary: Optional[str] = None
    content_snippet: Optional[str] = None
    diseases: List[str] = []
    
    # All metadata as flexible JSON
    metadata: Dict[str, Any] = {}
    
    # Highlight information if available
    highlights: Optional[Dict[str, List[str]]] = None


class UnifiedSearchResponse(BaseModel):
    """Unified search response"""
    results: List[UnifiedSearchResult]
    total: int
    limit: int
    offset: int
    query: Optional[str]
    execution_time_ms: int
    facets: Optional[List[SearchFacets]] = None
    suggested_filters: Optional[Dict[str, Any]] = None
    columns: Optional[List[Dict[str, Any]]] = None  # Dynamic column configuration


def build_metadata_conditions(metadata_filters: Dict[str, Any], param_count: int) -> tuple[str, list, int]:
    """
    Build SQL conditions for metadata filters supporting MongoDB-style operators
    
    Supported operators:
    - $eq: Exact match (default if no operator)
    - $ne: Not equal
    - $in: Value in array
    - $nin: Value not in array
    - $contains: JSONB contains (for arrays)
    - $exists: Field exists
    - $gt, $gte, $lt, $lte: Comparison operators
    - $regex: Regular expression match
    """
    conditions = []
    params = []
    
    for field, value in metadata_filters.items():
        # Handle dot notation for nested fields
        json_path = "->".join([f"'{part}'" for part in field.split(".")])
        base_path = f"metadata->{json_path}"
        
        if isinstance(value, dict) and any(k.startswith("$") for k in value.keys()):
            # Handle operators
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
                        # Array contains all values
                        conditions.append(f"{base_path} @> ${param_count}::jsonb")
                        params.append(json.dumps(op_value))
                        param_count += 1
                    else:
                        # Array contains value
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
                    # Handle date strings
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
            # Simple equality
            conditions.append(f"{base_path} = ${param_count}")
            params.append(json.dumps(value) if not isinstance(value, (str, int, float, bool)) else value)
            param_count += 1
    
    return " AND ".join(conditions), params, param_count


async def build_search_query(search_query: UnifiedSearchQuery) -> tuple[str, list]:
    """Build the main search query"""
    
    # Base query
    sql = """
        WITH search_results AS (
            SELECT DISTINCT 
                d.id,
                d.title,
                d.url,
                d.summary,
                d.content,
                d.created_at,
                d.doc_metadata,
                s.name as source_name,
                s.category as source_category,
                ARRAY(
                    SELECT dis.name 
                    FROM document_diseases dd 
                    JOIN diseases dis ON dd.disease_id = dis.id 
                    WHERE dd.document_id = d.id
                ) as disease_names
    """
    
    # Add relevance score if text search
    if search_query.q:
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
            WHERE 1=1
    """
    
    params = []
    param_count = 1
    
    # Text search
    if search_query.q:
        sql += f" AND to_tsvector('english', COALESCE(d.content, '') || ' ' || COALESCE(d.title, '')) @@ plainto_tsquery('english', ${param_count})"
        params.append(search_query.q)
        param_count += 1
    
    # Source filters
    if search_query.sources:
        sql += f" AND s.name = ANY(${param_count})"
        params.append(search_query.sources)
        param_count += 1
    
    if search_query.source_categories:
        sql += f" AND s.category = ANY(${param_count})"
        params.append(search_query.source_categories)
        param_count += 1
    
    # Disease filter
    if search_query.diseases:
        sql += f""" AND EXISTS (
            SELECT 1 FROM document_diseases dd
            JOIN diseases dis ON dd.disease_id = dis.id
            WHERE dd.document_id = d.id
            AND dis.name = ANY(${param_count})
        )"""
        params.append(search_query.diseases)
        param_count += 1
    
    # Metadata filters
    if search_query.metadata:
        metadata_sql, metadata_params, param_count = build_metadata_conditions(
            search_query.metadata, param_count
        )
        if metadata_sql:
            sql += f" AND {metadata_sql}"
            params.extend(metadata_params)
    
    sql += ")"  # Close CTE
    
    # Main select from CTE
    sql += """
        SELECT * FROM search_results
    """
    
    # Sorting
    if search_query.sort_by == "relevance" and search_query.q:
        sql += " ORDER BY rank DESC, created_at DESC"
    elif search_query.sort_by == "date":
        sql += f" ORDER BY created_at {search_query.sort_order.upper()}"
    elif search_query.sort_by and "." in search_query.sort_by:
        # Sort by metadata field
        json_path = "->".join([f"'{part}'" for part in search_query.sort_by.split(".")])
        sql += f" ORDER BY metadata->{json_path} {search_query.sort_order.upper()}"
    else:
        sql += " ORDER BY created_at DESC"
    
    # Pagination
    sql += f" LIMIT ${param_count} OFFSET ${param_count + 1}"
    params.extend([search_query.limit, search_query.offset])
    
    return sql, params


async def generate_facets(
    conn: asyncpg.Connection,
    search_query: UnifiedSearchQuery,
    base_conditions: str,
    base_params: list
) -> List[SearchFacets]:
    """Generate facet counts for requested fields"""
    
    if not search_query.facets:
        return []
    
    facets = []
    
    for facet_field in search_query.facets:
        if facet_field == "source":
            # Special handling for source facet
            facet_sql = f"""
                SELECT s.name as value, COUNT(DISTINCT d.id) as count
                FROM documents d
                JOIN sources s ON d.source_id = s.id
                WHERE 1=1 {base_conditions}
                GROUP BY s.name
                ORDER BY count DESC
                LIMIT 20
            """
        elif facet_field == "source_category":
            # Special handling for source category
            facet_sql = f"""
                SELECT s.category as value, COUNT(DISTINCT d.id) as count
                FROM documents d
                JOIN sources s ON d.source_id = s.id
                WHERE 1=1 {base_conditions}
                GROUP BY s.category
                ORDER BY count DESC
            """
        elif facet_field == "disease":
            # Special handling for diseases
            facet_sql = f"""
                SELECT dis.name as value, COUNT(DISTINCT dd.document_id) as count
                FROM document_diseases dd
                JOIN diseases dis ON dd.disease_id = dis.id
                JOIN documents d ON dd.document_id = d.id
                WHERE 1=1 {base_conditions.replace('d.', 'd.')}
                GROUP BY dis.name
                ORDER BY count DESC
                LIMIT 30
            """
        else:
            # Dynamic metadata field faceting
            if "." in facet_field:
                json_path = "->".join([f"'{part}'" for part in facet_field.split(".")])
            else:
                json_path = f"'{facet_field}'"
            
            # Check if array field
            type_check = await conn.fetchval(
                f"SELECT jsonb_typeof(metadata->{json_path}) FROM documents WHERE metadata->{json_path} IS NOT NULL LIMIT 1"
            )
            
            if type_check == "array":
                facet_sql = f"""
                    SELECT value, COUNT(*) as count
                    FROM (
                        SELECT jsonb_array_elements_text(metadata->{json_path}) as value
                        FROM documents d
                        JOIN sources s ON d.source_id = s.id
                        WHERE metadata->{json_path} IS NOT NULL
                        {base_conditions}
                    ) t
                    GROUP BY value
                    ORDER BY count DESC
                    LIMIT 20
                """
            else:
                facet_sql = f"""
                    SELECT metadata->>{json_path} as value, COUNT(*) as count
                    FROM documents d
                    JOIN sources s ON d.source_id = s.id
                    WHERE metadata->{json_path} IS NOT NULL
                    {base_conditions}
                    GROUP BY metadata->>{json_path}
                    ORDER BY count DESC
                    LIMIT 20
                """
        
        # Execute facet query
        facet_results = await conn.fetch(facet_sql, *base_params)
        
        if facet_results:
            facets.append(SearchFacets(
                field=facet_field,
                values=[
                    FacetValue(value=row['value'], count=row['count'])
                    for row in facet_results
                ],
                total_unique=len(facet_results)
            ))
    
    return facets


def generate_columns_for_results(results: List[UnifiedSearchResult]) -> List[Dict[str, Any]]:
    """Generate dynamic column configuration based on search results"""
    
    # Base columns always shown
    columns = [
        {"key": "title", "label": "Title", "sortable": True, "width": "300"},
        {"key": "source", "label": "Source", "sortable": True, "width": "150"},
        {"key": "created_at", "label": "Date", "sortable": True, "width": "120", "render": "date"}
    ]
    
    if not results:
        return columns
    
    # Analyze metadata fields from actual results
    metadata_fields = {}
    categories = set()
    
    # Sample up to 20 results to determine common fields
    for result in results[:20]:
        if result.source_category:
            categories.add(result.source_category)
        
        # Collect metadata fields and their types
        for field, value in result.metadata.items():
            if field not in metadata_fields:
                metadata_fields[field] = {
                    "count": 0,
                    "type": None,
                    "sample_values": []
                }
            
            metadata_fields[field]["count"] += 1
            
            # Determine field type from value
            if isinstance(value, list):
                metadata_fields[field]["type"] = "list"
            elif isinstance(value, (int, float)):
                metadata_fields[field]["type"] = "number"
            elif isinstance(value, bool):
                metadata_fields[field]["type"] = "boolean"
            else:
                metadata_fields[field]["type"] = "string"
            
            # Collect sample values
            if len(metadata_fields[field]["sample_values"]) < 3 and value:
                metadata_fields[field]["sample_values"].append(value)
    
    # If mixed categories, show summary
    if len(categories) > 1:
        columns.append({"key": "summary", "label": "Summary", "sortable": False, "width": "400"})
        return columns
    
    # Add columns for most common metadata fields
    # Sort by frequency and select top fields
    sorted_fields = sorted(
        metadata_fields.items(),
        key=lambda x: x[1]["count"],
        reverse=True
    )
    
    # Add up to 4 additional columns based on frequency
    added_columns = 0
    for field_name, field_info in sorted_fields:
        if added_columns >= 4:
            break
        
        # Skip fields that are too sparse
        if field_info["count"] < len(results) * 0.5:
            continue
        
        # Generate column configuration
        col_config = {
            "key": f"metadata.{field_name}",
            "label": field_name.replace('_', ' ').title(),
            "sortable": False,
            "width": "150"
        }
        
        # Set render type based on field type and content
        if field_info["type"] == "list":
            col_config["render"] = "list"
            col_config["maxItems"] = 3
            col_config["width"] = "200"
        elif field_info["type"] == "number":
            col_config["render"] = "number"
            col_config["width"] = "100"
        elif field_name.endswith("_url") or field_name == "doi":
            col_config["render"] = "link"
        elif field_name.endswith("_status") or field_name == "phase":
            col_config["render"] = "badge"
        
        columns.append(col_config)
        added_columns += 1
    
    # Always add summary if we have room
    if added_columns < 4:
        columns.append({"key": "summary", "label": "Summary", "sortable": False, "width": "300"})
    
    return columns


@router.post("/unified", response_model=UnifiedSearchResponse)
async def unified_search(search_query: UnifiedSearchQuery):
    """
    Unified search endpoint with full JSONB metadata support.
    
    Features:
    - MongoDB-style query operators for metadata filtering
    - Dynamic faceting on any metadata field
    - Flexible sorting by any field
    - Configurable return fields
    - Disease and source filtering
    - Full-text search with ranking
    
    Example metadata queries:
    ```json
    {
        "metadata": {
            "publication_date": {"$gte": "2023-01-01"},
            "authors": {"$contains": "Smith"},
            "phase": {"$in": ["Phase 2", "Phase 3"]},
            "pmid": {"$exists": true}
        }
    }
    ```
    """
    start_time = time.time()
    
    async with get_pg_connection() as conn:
        # Build and execute main search query
        sql, params = await build_search_query(search_query)
        results = await conn.fetch(sql, *params)
        
        # Get total count (remove pagination)
        count_sql = sql.split("ORDER BY")[0].replace(
            "SELECT * FROM search_results",
            "SELECT COUNT(*) FROM search_results"
        )
        # Remove limit/offset params
        count_params = params[:-2] if len(params) >= 2 else params
        total_count = await conn.fetchval(count_sql, *count_params)
        
        # Generate facets if requested
        facets = None
        if search_query.facets:
            # Build base conditions for faceting (without pagination)
            base_conditions = ""
            if search_query.q:
                base_conditions += f" AND to_tsvector('english', COALESCE(d.content, '') || ' ' || COALESCE(d.title, '')) @@ plainto_tsquery('english', ${params.index(search_query.q) + 1})"
            if search_query.sources:
                base_conditions += f" AND s.name = ANY(${params.index(search_query.sources) + 1})"
            if search_query.source_categories:
                base_conditions += f" AND s.category = ANY(${params.index(search_query.source_categories) + 1})"
            # Add other conditions...
            
            facets = await generate_facets(conn, search_query, base_conditions, count_params)
        
        # Process results
        search_results = []
        for row in results:
            # Parse metadata
            metadata = json.loads(row['doc_metadata']) if row['doc_metadata'] else {}
            
            # Filter metadata fields if requested
            if search_query.return_fields:
                filtered_metadata = {}
                for field in search_query.return_fields:
                    if "." in field:
                        # Handle nested fields
                        parts = field.split(".")
                        value = metadata
                        for part in parts:
                            if isinstance(value, dict) and part in value:
                                value = value[part]
                            else:
                                value = None
                                break
                        if value is not None:
                            filtered_metadata[field] = value
                    elif field in metadata:
                        filtered_metadata[field] = metadata[field]
                metadata = filtered_metadata
            
            result = UnifiedSearchResult(
                id=row['id'],
                title=row['title'] or 'Untitled',
                url=row['url'],
                source=row['source_name'],
                source_category=row['source_category'],
                created_at=row['created_at'],
                relevance_score=float(row['rank']) if row.get('rank') else 1.0,
                summary=row['summary'],
                content_snippet=(row['content'][:200] + '...') if row['content'] else None,
                diseases=row['disease_names'] or [],
                metadata=metadata
            )
            
            search_results.append(result)
        
        execution_time = int((time.time() - start_time) * 1000)
        
        # Generate columns based on results
        columns = generate_columns_for_results(search_results)
        
        return UnifiedSearchResponse(
            results=search_results,
            total=total_count or 0,
            limit=search_query.limit,
            offset=search_query.offset,
            query=search_query.q,
            execution_time_ms=execution_time,
            facets=facets,
            columns=columns
        )


@router.get("/unified/suggest")
async def suggest_filters(
    source_category: Optional[str] = None,
    source: Optional[str] = None
) -> Dict[str, Any]:
    """
    Get suggested filters based on source type.
    Returns common metadata fields and their types for building dynamic UIs.
    """
    
    async with get_pg_connection() as conn:
        # Build source filter
        where_clause = "WHERE 1=1"
        params = []
        param_count = 1
        
        if source:
            where_clause += f" AND s.name = ${param_count}"
            params.append(source)
            param_count += 1
        elif source_category:
            where_clause += f" AND s.category = ${param_count}"
            params.append(source_category)
            param_count += 1
        
        # Get common metadata fields
        field_sql = f"""
            WITH metadata_fields AS (
                SELECT DISTINCT jsonb_object_keys(metadata) as field
                FROM documents d
                JOIN sources s ON d.source_id = s.id
                {where_clause}
            )
            SELECT field, 
                   COUNT(*) as doc_count,
                   (SELECT jsonb_typeof(metadata->field) 
                    FROM documents d2 
                    JOIN sources s2 ON d2.source_id = s2.id
                    WHERE d2.metadata->field IS NOT NULL 
                    {where_clause.replace('$1', '$' + str(param_count))}
                    LIMIT 1) as field_type
            FROM metadata_fields
            GROUP BY field
            ORDER BY doc_count DESC
        """
        
        if params:
            params.extend(params)  # Duplicate params for subquery
        
        fields = await conn.fetch(field_sql, *params)
        
        # Build suggested filters structure
        suggestions = {
            "fields": [],
            "operators": {
                "string": ["$eq", "$ne", "$regex", "$exists"],
                "number": ["$eq", "$ne", "$gt", "$gte", "$lt", "$lte", "$exists"],
                "array": ["$contains", "$exists"],
                "object": ["$exists"],
                "boolean": ["$eq", "$ne", "$exists"]
            }
        }
        
        for row in fields:
            field_info = {
                "name": row['field'],
                "type": row['field_type'],
                "document_count": row['doc_count'],
                "operators": suggestions["operators"].get(row['field_type'], ["$exists"])
            }
            
            # Get sample values for certain fields
            if row['field_type'] in ['string', 'number'] and row['doc_count'] < 1000:
                sample_sql = f"""
                    SELECT DISTINCT metadata->>'{row['field']}' as value
                    FROM documents d
                    JOIN sources s ON d.source_id = s.id
                    WHERE metadata->>'{row['field']}' IS NOT NULL
                    {where_clause}
                    LIMIT 10
                """
                samples = await conn.fetch(sample_sql, *params)
                field_info['sample_values'] = [s['value'] for s in samples]
            
            suggestions["fields"].append(field_info)
        
        return suggestions


@router.get("/unified/export")
async def export_unified_search(
    format: str = "json",
    q: Optional[str] = None,
    sources: Optional[List[str]] = None,
    source_categories: Optional[List[str]] = None,
    diseases: Optional[List[str]] = None,
    limit: int = 100
):
    """Export search results in various formats"""
    
    # Build search query
    search_query = UnifiedSearchQuery(
        q=q,
        sources=sources,
        source_categories=source_categories,
        diseases=diseases,
        limit=limit,
        offset=0
    )
    
    # Execute search
    search_results = await unified_search(search_query)
    
    if format == "csv":
        # Return CSV format
        import csv
        import io
        
        output = io.StringIO()
        writer = csv.DictWriter(
            output,
            fieldnames=["id", "title", "url", "source", "source_category", "created_at", "summary"]
        )
        writer.writeheader()
        
        for result in search_results.results:
            writer.writerow({
                "id": result.id,
                "title": result.title,
                "url": result.url,
                "source": result.source,
                "source_category": result.source_category,
                "created_at": result.created_at.isoformat() if result.created_at else "",
                "summary": result.summary[:200] if result.summary else ""
            })
        
        from fastapi.responses import Response
        return Response(
            content=output.getvalue(),
            media_type="text/csv",
            headers={"Content-Disposition": "attachment; filename=search_results.csv"}
        )
    
    else:  # JSON format
        results = []
        for result in search_results.results:
            results.append({
                "id": result.id,
                "title": result.title,
                "url": result.url,
                "source": result.source,
                "source_category": result.source_category,
                "created_at": result.created_at.isoformat() if result.created_at else None,
                "summary": result.summary,
                "metadata": result.metadata,
                "diseases": result.diseases
            })
        
        return {"total": len(results), "results": results}


@router.get("/filters")
async def get_filters(
    category: Optional[str] = None
):
    """Get available filter options - compatibility endpoint for frontend"""
    
    async with get_pg_connection() as conn:
        filters = {
            "categories": [],
            "sources": [],
            "diseases": [],
            "metadata_fields": {}
        }
        
        # Get categories from sources table (not documents)
        category_query = """
            SELECT DISTINCT s.category, COUNT(s.id) as source_count
            FROM sources s
            WHERE s.is_active = true AND s.category IS NOT NULL
            GROUP BY s.category
            ORDER BY s.category
        """
        
        category_results = await conn.fetch(category_query)
        
        # Get document counts per category
        doc_count_query = """
            SELECT s.category, COUNT(DISTINCT d.id) as doc_count
            FROM sources s
            LEFT JOIN documents d ON s.id = d.source_id
            WHERE s.is_active = true AND s.category IS NOT NULL
            GROUP BY s.category
        """
        doc_counts = await conn.fetch(doc_count_query)
        doc_count_map = {row['category']: row['doc_count'] for row in doc_counts}
        
        filters["categories"] = [
            {
                "value": row['category'], 
                "label": row['category'].title(), 
                "count": doc_count_map.get(row['category'], 0),
                "source_count": row['source_count']
            }
            for row in category_results
        ]
        
        # Get sources
        source_query = """
            SELECT s.name, s.category, COUNT(d.id) as doc_count
            FROM sources s
            LEFT JOIN documents d ON s.id = d.source_id
            WHERE s.is_active = true
            GROUP BY s.name, s.category
            ORDER BY s.name
        """
        
        source_results = await conn.fetch(source_query)
        filters["sources"] = [
            {
                "value": row['name'],
                "category": row['category'],
                "document_count": row['doc_count']
            }
            for row in source_results
        ]
        
        # Get ALL diseases from diseases table (not just ones with documents)
        disease_query = """
            SELECT 
                dis.id,
                dis.name,
                dis.category,
                COUNT(DISTINCT dd.document_id) as doc_count
            FROM diseases dis
            LEFT JOIN document_diseases dd ON dis.id = dd.disease_id
            GROUP BY dis.id, dis.name, dis.category
            ORDER BY 
                CASE WHEN COUNT(dd.document_id) > 0 THEN 0 ELSE 1 END,  -- Show diseases with docs first
                doc_count DESC,
                dis.name ASC
            LIMIT 100
        """
        
        disease_results = await conn.fetch(disease_query)
        filters["diseases"] = [
            {
                "value": row['name'], 
                "count": row['doc_count'],
                "category": row['category']
            }
            for row in disease_results
        ]
        
        # Get metadata fields dynamically from database
        if category:
            # Get actual metadata fields from documents in this category
            metadata_query = """
                WITH metadata_fields AS (
                    SELECT DISTINCT jsonb_object_keys(d.doc_metadata) as field
                    FROM documents d
                    JOIN sources s ON d.source_id = s.id
                    WHERE s.category = $1
                )
                SELECT 
                    field,
                    (SELECT jsonb_typeof(metadata->field) 
                     FROM documents d2 
                     JOIN sources s2 ON d2.source_id = s2.id
                     WHERE d2.metadata->field IS NOT NULL 
                     AND s2.category = $1
                     LIMIT 1) as field_type,
                    COUNT(*) as usage_count
                FROM metadata_fields
                GROUP BY field
                ORDER BY usage_count DESC
            """
            
            field_results = await conn.fetch(metadata_query, category)
            
            # Build metadata fields dynamically
            for row in field_results:
                if row['field'] and row['field_type']:
                    # Generate description based on field name
                    description = row['field'].replace('_', ' ').title()
                    
                    filters["metadata_fields"][row['field']] = {
                        "type": row['field_type'],
                        "description": description,
                        "usage_count": row['usage_count']
                    }
        
        return filters