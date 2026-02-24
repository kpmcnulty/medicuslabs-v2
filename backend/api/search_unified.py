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
                    to_tsvector('english', COALESCE(d.title, '') || ' ' || COALESCE(d.content, '') || ' ' || COALESCE(d.summary, '')),
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
        sql += f" AND to_tsvector('english', COALESCE(d.title, '') || ' ' || COALESCE(d.content, '') || ' ' || COALESCE(d.summary, '')) @@ plainto_tsquery('english', ${param_count})"
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

    # Process column filters from table UI
    if search_query.columnFilters:
        for cf in search_query.columnFilters:
            col_id = cf.get("id", "")
            filter_val = cf.get("value", {})
            if not filter_val or not isinstance(filter_val, dict):
                continue
            
            conditions = filter_val.get("conditions", [])
            join_op = filter_val.get("joinOperator", "AND")
            
            col_conditions = []
            for cond in conditions:
                op = cond.get("operator", "contains")
                val = cond.get("value", "")
                if val == "" and op not in ("blank", "notBlank"):
                    continue
                
                # Determine if this is a metadata field or base field
                if col_id.startswith("metadata."):
                    json_field = col_id.replace("metadata.", "")
                    field_ref = f"d.doc_metadata->>'{json_field}'"
                elif col_id == "title":
                    field_ref = "d.title"
                elif col_id == "source":
                    field_ref = "s.name"
                elif col_id == "source_category":
                    field_ref = "s.category"
                elif col_id == "created_date":
                    # Use source_updated_at as the unified, always-clean date
                    field_ref = "d.source_updated_at::date"
                elif col_id == "diseases":
                    # Special handling for diseases array
                    if op == "contains":
                        sql += f""" AND EXISTS (
                            SELECT 1 FROM document_diseases dd2
                            JOIN diseases dis2 ON dd2.disease_id = dis2.id
                            WHERE dd2.document_id = d.id
                            AND dis2.name ILIKE ${param_count}
                        )"""
                        params.append(f"%{val}%")
                        param_count += 1
                    continue
                else:
                    field_ref = f"d.{col_id}"
                
                if op == "contains":
                    col_conditions.append(f"{field_ref} ILIKE ${param_count}")
                    params.append(f"%{val}%")
                    param_count += 1
                elif op == "equals":
                    col_conditions.append(f"{field_ref} = ${param_count}")
                    params.append(str(val))
                    param_count += 1
                elif op == "notEqual":
                    col_conditions.append(f"{field_ref} != ${param_count}")
                    params.append(str(val))
                    param_count += 1
                elif op == "startsWith":
                    col_conditions.append(f"{field_ref} ILIKE ${param_count}")
                    params.append(f"{val}%")
                    param_count += 1
                elif op == "endsWith":
                    col_conditions.append(f"{field_ref} ILIKE ${param_count}")
                    params.append(f"%{val}")
                    param_count += 1
                elif op == "notContains":
                    col_conditions.append(f"{field_ref} NOT ILIKE ${param_count}")
                    params.append(f"%{val}%")
                    param_count += 1
                elif op == "greaterThan":
                    col_conditions.append(f"({field_ref})::numeric > ${param_count}::numeric")
                    params.append(val)
                    param_count += 1
                elif op == "lessThan":
                    col_conditions.append(f"({field_ref})::numeric < ${param_count}::numeric")
                    params.append(val)
                    param_count += 1
                elif op in ("before", "after"):
                    cmp = "<" if op == "before" else ">"
                    from datetime import date as date_type
                    try:
                        date_val = date_type.fromisoformat(str(val))
                    except (ValueError, TypeError):
                        continue
                    col_conditions.append(f"{field_ref} {cmp} ${param_count}")
                    params.append(date_val)
                    param_count += 1
                elif op == "blank":
                    col_conditions.append(f"({field_ref} IS NULL OR {field_ref} = '')")
                elif op == "notBlank":
                    col_conditions.append(f"({field_ref} IS NOT NULL AND {field_ref} != '')")
            
            if col_conditions:
                joined = f" {join_op} ".join(col_conditions)
                sql += f" AND ({joined})"

    sql += ")"
    sql += "\n        SELECT *, COUNT(*) OVER() as total_count FROM search_results\n"

    # Sorting
    if search_query.sort_by == "relevance" and search_query.q:
        sql += " ORDER BY rank DESC, created_at DESC"
    elif search_query.sort_by in ("date", "created_date"):
        sql += f" ORDER BY source_updated_at {search_query.sort_order.upper()} NULLS LAST"
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

        # Total count comes from the window function
        total_count = results[0]['total_count'] if results else 0

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


@router.get("/counts")
async def get_search_counts(
    diseases: Optional[str] = None,
    q: Optional[str] = None
):
    """
    Get counts of results per source category for given filters.

    Example: /api/search/counts?diseases=Multiple+Sclerosis&q=treatment
    Returns: {"publications": 847, "trials": 23, "community": 156, "safety": 1204}
    """
    async with get_pg_connection() as conn:
        # Build the base WHERE clause
        where_conditions = ["1=1"]
        params = []
        param_count = 1

        # Parse diseases parameter (comma-separated list)
        if diseases:
            disease_list = [d.strip() for d in diseases.split(',')]
            where_conditions.append(f"""
                EXISTS (
                    SELECT 1 FROM document_diseases dd
                    JOIN diseases dis ON dd.disease_id = dis.id
                    WHERE dd.document_id = d.id
                    AND dis.name = ANY(${param_count})
                )
            """)
            params.append(disease_list)
            param_count += 1

        # Add text search if provided
        if q:
            where_conditions.append(f"""
                to_tsvector('english', COALESCE(d.title, '') || ' ' || COALESCE(d.content, '') || ' ' || COALESCE(d.summary, ''))
                @@ plainto_tsquery('english', ${param_count})
            """)
            params.append(q)
            param_count += 1

        where_clause = " AND ".join(where_conditions)

        # Query to get counts per category
        query = f"""
            SELECT
                s.category,
                COUNT(DISTINCT d.id) as count
            FROM documents d
            JOIN sources s ON d.source_id = s.id
            WHERE {where_clause}
            GROUP BY s.category
        """

        results = await conn.fetch(query, *params)

        # Map results to the expected format
        counts = {
            "publications": 0,
            "trials": 0,
            "community": 0,
            "safety": 0
        }

        for row in results:
            if row['category'] in counts:
                counts[row['category']] = row['count']

        return counts


@router.get("/unified/suggest")
async def get_field_suggestions(source_category: Optional[str] = None, source: Optional[str] = None):
    """Return field metadata for the QueryBuilder"""

    base_fields = [
        {"name": "title", "label": "Title", "type": "string", "category": "core", "operators": ["contains", "equals", "not_equals"]},
        {"name": "source", "label": "Source", "type": "string", "category": "core", "operators": ["equals", "not_equals", "in"],
         "sample_values": []},
        {"name": "source_category", "label": "Category", "type": "string", "category": "core", "operators": ["equals", "not_equals", "in"],
         "sample_values": [{"value": "publications"}, {"value": "trials"}, {"value": "community"}, {"value": "safety"}]},
        {"name": "created_date", "label": "Date", "type": "date", "category": "core", "operators": ["equals", "greater_than", "less_than", "between"]},
        {"name": "diseases", "label": "Diseases", "type": "array", "category": "core", "operators": ["contains", "equals"]},
    ]

    # Add common metadata fields per source category
    metadata_fields = {
        "publications": [
            {"name": "metadata.authors", "label": "Authors", "type": "array", "category": "metadata", "operators": ["contains"]},
            {"name": "metadata.journal", "label": "Journal", "type": "string", "category": "metadata", "operators": ["equals", "contains"]},
            {"name": "metadata.publication_date", "label": "Publication Date", "type": "date", "category": "metadata", "operators": ["equals", "greater_than", "less_than"]},
            {"name": "metadata.article_types", "label": "Article Type", "type": "array", "category": "metadata", "operators": ["contains"]},
            {"name": "metadata.keywords", "label": "Keywords", "type": "array", "category": "metadata", "operators": ["contains"]},
        ],
        "trials": [
            {"name": "metadata.phase", "label": "Phase", "type": "string", "category": "metadata", "operators": ["equals", "in"]},
            {"name": "metadata.status", "label": "Status", "type": "string", "category": "metadata", "operators": ["equals", "in"]},
            {"name": "metadata.sponsor", "label": "Sponsor", "type": "string", "category": "metadata", "operators": ["equals", "contains"]},
            {"name": "metadata.study_type", "label": "Study Type", "type": "string", "category": "metadata", "operators": ["equals", "in"]},
            {"name": "metadata.enrollment", "label": "Enrollment", "type": "number", "category": "metadata", "operators": ["equals", "greater_than", "less_than"]},
        ],
        "community": [
            {"name": "metadata.subreddit", "label": "Subreddit", "type": "string", "category": "metadata", "operators": ["equals"]},
            {"name": "metadata.score", "label": "Score", "type": "number", "category": "metadata", "operators": ["greater_than", "less_than"]},
            {"name": "metadata.num_comments", "label": "Comments", "type": "number", "category": "metadata", "operators": ["greater_than", "less_than"]},
        ],
        "safety": [
            {"name": "metadata.serious", "label": "Serious", "type": "boolean", "category": "metadata", "operators": ["equals"]},
            {"name": "metadata.reactions", "label": "Reactions", "type": "array", "category": "metadata", "operators": ["contains"]},
            {"name": "metadata.patient_age", "label": "Patient Age", "type": "string", "category": "metadata", "operators": ["equals"]},
        ],
    }

    fields = base_fields.copy()
    if source_category and source_category in metadata_fields:
        fields.extend(metadata_fields[source_category])
    else:
        # Include all metadata fields
        for cat_fields in metadata_fields.values():
            fields.extend(cat_fields)

    # Populate source sample values
    async with get_pg_connection() as conn:
        sources = await conn.fetch("SELECT DISTINCT name FROM sources WHERE is_active = true ORDER BY name")
        for f in fields:
            if f["name"] == "source":
                f["sample_values"] = [{"value": r["name"]} for r in sources]

    categories = {
        "core": "Core Fields",
        "metadata": "Metadata Fields",
    }

    operators = {
        "equals": {"label": "Equals", "icon": "="},
        "not_equals": {"label": "Not Equals", "icon": "≠"},
        "contains": {"label": "Contains", "icon": "⊃"},
        "greater_than": {"label": "Greater Than", "icon": ">"},
        "less_than": {"label": "Less Than", "icon": "<"},
        "between": {"label": "Between", "icon": "↔"},
        "in": {"label": "In", "icon": "∈"},
    }

    return {"fields": fields, "categories": categories, "operators": operators}
