from fastapi import APIRouter, HTTPException
from typing import List, Optional, Dict, Any
from datetime import datetime
import asyncpg
from pydantic import BaseModel, Field
import json
import time
import logging

from core.database import get_pg_connection
from models.schemas import SourceType

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/search", tags=["search"])


class UnifiedSearchQuery(BaseModel):
    """Simplified unified search query"""
    q: Optional[str] = Field(None, description="Search query text")
    sources: Optional[List[str]] = Field(None, description="Filter by source names")
    source_categories: Optional[List[str]] = Field(None, description="Filter by source categories")
    diseases: Optional[List[str]] = Field(None, description="Filter by disease names")
    metadata: Optional[Dict[str, Any]] = Field(None, description="Metadata filters")
    columnFilters: Optional[List[Dict[str, Any]]] = Field(None, description="Column filters from table UI")
    limit: int = Field(50, le=10000)
    offset: int = Field(0, ge=0)
    sort_by: Optional[str] = Field("relevance", description="Sort field")
    sort_order: str = Field("desc", description="Sort order: asc or desc")


class UnifiedSearchResult(BaseModel):
    """Unified search result"""
    id: int
    title: str
    url: str
    source: str
    source_category: Optional[str]
    created_at: datetime
    relevance_score: float
    summary: Optional[str] = None
    content_snippet: Optional[str] = None
    diseases: List[str] = []
    created_date: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    source_updated_at: Optional[datetime] = None
    metadata: Dict[str, Any] = {}


class UnifiedSearchResponse(BaseModel):
    """Unified search response"""
    results: List[UnifiedSearchResult]
    total: int
    limit: int
    offset: int
    query: Optional[str]
    execution_time_ms: int
    columns: Optional[List[Dict[str, Any]]] = None


def build_metadata_conditions(metadata_filters: Dict[str, Any], param_count: int) -> tuple[str, list, int]:
    """Build SQL conditions for metadata filters with basic operators"""
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
                elif op == "$gt":
                    conditions.append(f"({base_path})::numeric > ${param_count}::numeric")
                    params.append(op_value)
                    param_count += 1
                elif op == "$gte":
                    conditions.append(f"({base_path})::numeric >= ${param_count}::numeric")
                    params.append(op_value)
                    param_count += 1
                elif op == "$lt":
                    conditions.append(f"({base_path})::numeric < ${param_count}::numeric")
                    params.append(op_value)
                    param_count += 1
                elif op == "$lte":
                    conditions.append(f"({base_path})::numeric <= ${param_count}::numeric")
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
        else:
            conditions.append(f"{base_path} = ${param_count}")
            params.append(json.dumps(value) if not isinstance(value, (str, int, float, bool)) else value)
            param_count += 1

    return " AND ".join(conditions), params, param_count


async def build_search_query(search_query: UnifiedSearchQuery) -> tuple[str, list]:
    """Build the main search query"""

    sql = """
        WITH search_results AS (
            SELECT DISTINCT
                d.id,
                d.title,
                d.url,
                d.summary,
                d.content,
                d.created_at,
                d.updated_at,
                d.source_updated_at,
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

    if search_query.q:
        sql += f" AND to_tsvector('english', COALESCE(d.content, '') || ' ' || COALESCE(d.title, '')) @@ plainto_tsquery('english', ${param_count})"
        params.append(search_query.q)
        param_count += 1

    if search_query.sources:
        sql += f" AND s.name = ANY(${param_count})"
        params.append(search_query.sources)
        param_count += 1

    if search_query.source_categories:
        sql += f" AND s.category = ANY(${param_count})"
        params.append(search_query.source_categories)
        param_count += 1

    if search_query.diseases:
        sql += f""" AND EXISTS (
            SELECT 1 FROM document_diseases dd
            JOIN diseases dis ON dd.disease_id = dis.id
            WHERE dd.document_id = d.id
            AND dis.name = ANY(${param_count})
        )"""
        params.append(search_query.diseases)
        param_count += 1

    if search_query.metadata:
        metadata_sql, metadata_params, param_count = build_metadata_conditions(
            search_query.metadata, param_count
        )
        if metadata_sql:
            sql += f" AND {metadata_sql}"
            params.extend(metadata_params)

    sql += ")"
    sql += "\n        SELECT * FROM search_results\n"

    # Sorting
    if search_query.sort_by == "relevance" and search_query.q:
        sql += " ORDER BY rank DESC, created_at DESC"
    elif search_query.sort_by == "date":
        sql += f" ORDER BY created_at {search_query.sort_order.upper()}"
    elif search_query.sort_by == "source":
        sql += f" ORDER BY source_name {search_query.sort_order.upper()}"
    elif search_query.sort_by == "title":
        sql += f" ORDER BY title {search_query.sort_order.upper()}"
    else:
        sql += " ORDER BY created_at DESC"

    sql += f" LIMIT ${param_count} OFFSET ${param_count + 1}"
    params.extend([search_query.limit, search_query.offset])

    return sql, params


@router.post("/unified", response_model=UnifiedSearchResponse)
async def unified_search(search_query: UnifiedSearchQuery):
    """
    Unified search endpoint with keyword search and metadata filtering.

    Example:
    ```json
    {
        "q": "diabetes treatment",
        "sources": ["PubMed"],
        "diseases": ["Type 2 Diabetes"],
        "metadata": {
            "publication_date": {"$gte": "2023-01-01"}
        },
        "limit": 50,
        "offset": 0
    }
    ```
    """
    start_time = time.time()

    async with get_pg_connection() as conn:
        sql, params = await build_search_query(search_query)

        logger.info(f"SQL Query: {sql[:200]}...")
        logger.info(f"Parameters: {params}")

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
            metadata = json.loads(row['doc_metadata']) if row['doc_metadata'] else {}

            # Extract created date based on source type
            created_date = None
            if metadata:
                if row['source_category'] == 'community':
                    posted_date_str = metadata.get('posted_date') or metadata.get('created_date')
                    if posted_date_str:
                        try:
                            created_date = datetime.fromisoformat(posted_date_str.replace('Z', '+00:00'))
                        except:
                            pass
                elif row['source_category'] == 'publications':
                    pub_date_str = metadata.get('publication_date')
                    if pub_date_str:
                        try:
                            created_date = datetime.strptime(pub_date_str, "%Y-%m-%d")
                        except:
                            pass
                elif row['source_category'] == 'trials':
                    start_date_str = metadata.get('start_date') or metadata.get('study_start_date')
                    if start_date_str:
                        try:
                            created_date = datetime.strptime(start_date_str, "%Y-%m-%d")
                        except:
                            pass

            if not created_date:
                created_date = row['created_at']

            result = UnifiedSearchResult(
                id=row['id'],
                title=row['title'] or 'Untitled',
                url=row['url'],
                source=row['source_name'],
                source_category=row['source_category'],
                created_at=row['created_at'],
                created_date=created_date,
                updated_at=row['updated_at'],
                source_updated_at=row['source_updated_at'],
                relevance_score=float(row['rank']) if row.get('rank') else 1.0,
                summary=row['summary'],
                content_snippet=(row['content'][:200] + '...') if row['content'] else None,
                diseases=row['disease_names'] or [],
                metadata=metadata
            )

            search_results.append(result)

        execution_time = int((time.time() - start_time) * 1000)

        # Build column definitions from results (key/label format for frontend DynamicDataTable)
        base_columns = [
            {"key": "title", "label": "Title", "type": "string", "sortable": True, "width": "300", "inputType": "text"},
            {"key": "source", "label": "Source", "type": "string", "sortable": True, "width": "150", "inputType": "select", "fetchOptions": True, "optionsEndpoint": "/api/search/filter-options?field=source"},
            {"key": "source_category", "label": "Category", "type": "string", "sortable": True, "width": "120", "inputType": "select", "fetchOptions": True, "optionsEndpoint": "/api/search/filter-options?field=source_category"},
            {"key": "diseases", "label": "Diseases", "type": "array", "width": "200", "inputType": "select", "fetchOptions": True, "optionsEndpoint": "/api/search/filter-options?field=diseases"},
            {"key": "created_date", "label": "Date", "type": "date", "sortable": True, "width": "120", "inputType": "date"},
            {"key": "url", "label": "URL", "type": "string", "width": "100"},
        ]

        # Add metadata columns from first few results
        metadata_fields = set()
        for r in search_results[:20]:
            for key in r.metadata.keys():
                metadata_fields.add(key)
        
        metadata_columns = [
            {"key": f"metadata.{f}", "label": f.replace("_", " ").title(), "type": "string", "width": "150", "inputType": "text"}
            for f in sorted(metadata_fields)
        ]

        return UnifiedSearchResponse(
            results=search_results,
            total=total_count or 0,
            limit=search_query.limit,
            offset=search_query.offset,
            query=search_query.q,
            execution_time_ms=execution_time,
            columns=base_columns + metadata_columns
        )


@router.get("/filter-options")
async def get_filter_options(field: str):
    """Get distinct values for a specific field for filtering"""
    async with get_pg_connection() as conn:
        # Base fields query from documents/sources table
        if field in ['source', 'source_name']:
            query = """
                SELECT s.name as value, s.name as label, COUNT(d.id) as count
                FROM sources s
                LEFT JOIN documents d ON s.id = d.source_id
                WHERE s.is_active = true
                GROUP BY s.name
                ORDER BY count DESC, s.name
                LIMIT 100
            """
            results = await conn.fetch(query)
        elif field == 'source_category':
            query = """
                SELECT s.category as value, s.category as label, COUNT(d.id) as count
                FROM sources s
                LEFT JOIN documents d ON s.id = d.source_id
                WHERE s.is_active = true AND s.category IS NOT NULL
                GROUP BY s.category
                ORDER BY count DESC
            """
            results = await conn.fetch(query)
        elif field == 'diseases':
            query = """
                SELECT dis.name as value, dis.name as label, COUNT(DISTINCT dd.document_id) as count
                FROM diseases dis
                LEFT JOIN document_diseases dd ON dis.id = dd.disease_id
                GROUP BY dis.name
                ORDER BY count DESC, dis.name
                LIMIT 100
            """
            results = await conn.fetch(query)
        else:
            # Metadata field - extract from doc_metadata JSONB
            # field should be like "publication_date" (without metadata. prefix)
            query = """
                SELECT DISTINCT
                    doc_metadata->>$1 as value,
                    doc_metadata->>$1 as label,
                    COUNT(*) as count
                FROM documents
                WHERE doc_metadata->>$1 IS NOT NULL
                GROUP BY doc_metadata->>$1
                ORDER BY count DESC
                LIMIT 100
            """
            results = await conn.fetch(query, field)

        options = [
            {
                "value": row['value'],
                "label": row['label'],
                "count": row['count']
            }
            for row in results if row['value']
        ]

        return {"options": options}


@router.get("/filters")
async def get_filters(category: Optional[str] = None):
    """Get available filter options"""

    async with get_pg_connection() as conn:
        filters = {
            "categories": [],
            "sources": [],
            "diseases": []
        }

        # Get categories
        category_query = """
            SELECT s.category, COUNT(DISTINCT d.id) as doc_count
            FROM sources s
            LEFT JOIN documents d ON s.id = d.source_id
            WHERE s.is_active = true AND s.category IS NOT NULL
            GROUP BY s.category
            ORDER BY s.category
        """
        category_results = await conn.fetch(category_query)
        filters["categories"] = [
            {
                "value": row['category'],
                "label": row['category'].title(),
                "count": row['doc_count']
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

        # Get diseases
        disease_query = """
            SELECT
                dis.name,
                dis.category,
                COUNT(DISTINCT dd.document_id) as doc_count
            FROM diseases dis
            LEFT JOIN document_diseases dd ON dis.id = dd.disease_id
            GROUP BY dis.name, dis.category
            ORDER BY doc_count DESC, dis.name ASC
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

        return filters
