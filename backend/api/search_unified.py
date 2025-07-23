from fastapi import APIRouter, HTTPException, Depends
from typing import List, Optional, Dict, Any, Union
from datetime import datetime
import asyncpg
from pydantic import BaseModel, Field
import json
import time
import logging
from sqlalchemy.ext.asyncio import AsyncSession
from dateutil import parser as date_parser

from core.database import get_db, get_pg_connection
from core.config import settings
from models.schemas import SourceType

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/search", tags=["search"])

def parse_date_value(value: Any) -> Any:
    """Parse date string to datetime object for PostgreSQL"""
    if isinstance(value, str):
        # Handle empty strings
        if not value or value.strip() == '':
            return None
        try:
            # Try to parse as date/datetime
            if "T" in value:
                # Full datetime string
                return datetime.fromisoformat(value.replace('Z', '+00:00'))
            else:
                # Date only string - parse with dateutil for flexibility
                parsed = date_parser.parse(value)
                # Return as datetime for PostgreSQL compatibility
                return datetime.combine(parsed.date(), datetime.min.time())
        except:
            # If parsing fails, return original value
            logger.warning(f"Failed to parse date value: {value}")
            return value
    return value


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
    
    # Column filters from table UI
    columnFilters: Optional[List[Dict[str, Any]]] = Field(None, description="Column-specific filters from table UI")
    
    # Search configuration
    search_type: str = Field("keyword", description="Search type: keyword, semantic, or hybrid")
    return_fields: Optional[List[str]] = Field(None, description="Specific fields to return from metadata")
    facets: Optional[List[str]] = Field(None, description="Fields to generate facet counts for")
    
    # Pagination
    limit: int = Field(50, le=10000)  # Allow up to 10k for exports
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
    created_date: Optional[datetime] = None  # When content was originally created
    updated_at: Optional[datetime] = None  # When we last updated it
    source_updated_at: Optional[datetime] = None  # When source last updated it
    
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
                    # Handle date strings for equality
                    if isinstance(op_value, str) and op_value.strip():
                        try:
                            if "T" in op_value:
                                parsed_date = datetime.fromisoformat(op_value.replace('Z', '+00:00'))
                                conditions.append(f"({base_path})::timestamp = ${param_count}::timestamp")
                                params.append(parsed_date)
                            else:
                                parsed_date = datetime.strptime(op_value, "%Y-%m-%d")
                                conditions.append(f"({base_path})::date = ${param_count}::date")
                                params.append(parsed_date)
                        except ValueError:
                            conditions.append(f"{base_path} = ${param_count}")
                            params.append(op_value)
                    else:
                        conditions.append(f"{base_path} = ${param_count}")
                        params.append(json.dumps(op_value) if not isinstance(op_value, (str, int, float, bool)) else op_value)
                    param_count += 1
                    
                elif op == "$ne":
                    # Handle date strings for not equal
                    if isinstance(op_value, str) and op_value.strip():
                        try:
                            if "T" in op_value:
                                parsed_date = datetime.fromisoformat(op_value.replace('Z', '+00:00'))
                                conditions.append(f"({base_path})::timestamp != ${param_count}::timestamp")
                                params.append(parsed_date)
                            else:
                                parsed_date = datetime.strptime(op_value, "%Y-%m-%d")
                                conditions.append(f"({base_path})::date != ${param_count}::date")
                                params.append(parsed_date)
                        except ValueError:
                            conditions.append(f"{base_path} != ${param_count}")
                            params.append(op_value)
                    else:
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
                    if isinstance(op_value, str) and op_value.strip():
                        try:
                            # Try to parse as datetime or date
                            if "T" in op_value:
                                # Full datetime string
                                parsed_date = datetime.fromisoformat(op_value.replace('Z', '+00:00'))
                                conditions.append(f"({base_path})::timestamp {sql_op} ${param_count}::timestamp")
                            else:
                                # Date only string
                                parsed_date = datetime.strptime(op_value, "%Y-%m-%d")
                                conditions.append(f"({base_path})::date {sql_op} ${param_count}::date")
                            params.append(parsed_date)
                        except ValueError:
                            # Not a date, treat as numeric
                            conditions.append(f"({base_path})::numeric {sql_op} ${param_count}::numeric")
                            params.append(op_value)
                    else:
                        # Empty string or non-string value
                        if isinstance(op_value, str):
                            # Skip empty string comparisons
                            continue
                        conditions.append(f"({base_path})::numeric {sql_op} ${param_count}::numeric")
                        params.append(op_value)
                    param_count += 1
                    
                elif op == "$regex":
                    conditions.append(f"{base_path}::text ~* ${param_count}")
                    params.append(op_value)
                    param_count += 1
                    
        else:
            # Simple equality
            if isinstance(value, str) and value.strip():
                try:
                    if "T" in value:
                        parsed_date = datetime.fromisoformat(value.replace('Z', '+00:00'))
                        conditions.append(f"({base_path})::timestamp = ${param_count}::timestamp")
                        params.append(parsed_date)
                    else:
                        parsed_date = datetime.strptime(value, "%Y-%m-%d")
                        conditions.append(f"({base_path})::date = ${param_count}::date")
                        params.append(parsed_date)
                except ValueError:
                    conditions.append(f"{base_path} = ${param_count}")
                    params.append(value)
            else:
                # Skip empty strings
                if isinstance(value, str) and not value.strip():
                    continue
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
    
    # Handle column filters from table UI
    if search_query.columnFilters:
        for filter_item in search_query.columnFilters:
            if 'id' in filter_item and 'value' in filter_item:
                column_id = filter_item['id']
                filter_value = filter_item['value']
                
                # Map column IDs to actual database fields
                column_mapping = {
                    'title': 'd.title',
                    'url': 'd.url',
                    'source': 's.name',
                    'created_at': 'd.created_at',
                    'updated_at': 'd.updated_at',
                    'source_updated_at': 'd.source_updated_at',
                    'summary': 'd.summary',
                    'created_date': """CASE 
                        WHEN s.category = 'community' THEN COALESCE((d.doc_metadata->>'posted_date')::timestamp, (d.doc_metadata->>'created_date')::timestamp)
                        WHEN s.category = 'publications' THEN (d.doc_metadata->>'publication_date')::date
                        WHEN s.category = 'trials' THEN COALESCE((d.doc_metadata->>'start_date')::date, (d.doc_metadata->>'study_start_date')::date)
                        ELSE d.created_at
                    END"""
                }
                
                # Use mapped column or metadata field
                column_ref = column_mapping.get(column_id, f"d.metadata->>'{column_id}'")
                
                # Convert column filter to metadata filter format
                if isinstance(filter_value, dict) and 'conditions' in filter_value:
                    # Advanced filter with conditions
                    conditions = filter_value['conditions']
                    join_op = filter_value.get('joinOperator', 'AND')
                    
                    column_conditions = []
                    for condition in conditions:
                        operator = condition.get('operator', 'contains')
                        value = condition.get('value')
                        
                        if value is None or value == '':
                            if operator in ['blank', 'notBlank']:
                                # Handle blank/not blank
                                if operator == 'blank':
                                    column_conditions.append(f"({column_ref} IS NULL OR {column_ref} = '')")
                                else:
                                    column_conditions.append(f"({column_ref} IS NOT NULL AND {column_ref} != '')")
                            continue
                        
                        # Map operators to SQL
                        if operator == 'contains':
                            column_conditions.append(f"{column_ref} ILIKE ${param_count}")
                            params.append(f'%{value}%')
                            param_count += 1
                        elif operator == 'notContains':
                            column_conditions.append(f"{column_ref} NOT ILIKE ${param_count}")
                            params.append(f'%{value}%')
                            param_count += 1
                        elif operator == 'equals':
                            column_conditions.append(f"{column_ref} = ${param_count}")
                            # Convert date strings for date columns
                            if column_id in ['created_at', 'created_date', 'updated_at', 'source_updated_at']:
                                params.append(parse_date_value(value))
                            else:
                                params.append(str(value))
                            param_count += 1
                        elif operator == 'notEqual':
                            column_conditions.append(f"{column_ref} != ${param_count}")
                            # Convert date strings for date columns
                            if column_id in ['created_at', 'created_date', 'updated_at', 'source_updated_at']:
                                params.append(parse_date_value(value))
                            else:
                                params.append(str(value))
                            param_count += 1
                        elif operator == 'startsWith':
                            column_conditions.append(f"{column_ref} ILIKE ${param_count}")
                            params.append(f'{value}%')
                            param_count += 1
                        elif operator == 'endsWith':
                            column_conditions.append(f"{column_ref} ILIKE ${param_count}")
                            params.append(f'%{value}')
                            param_count += 1
                        elif operator == 'greaterThan':
                            # For metadata fields, need to cast to numeric
                            if column_id not in column_mapping:
                                column_conditions.append(f"({column_ref})::numeric > ${param_count}::numeric")
                            else:
                                column_conditions.append(f"{column_ref} > ${param_count}")
                            # Convert date strings for date columns
                            if column_id in ['created_at', 'created_date', 'updated_at', 'source_updated_at']:
                                params.append(parse_date_value(value))
                            else:
                                params.append(value)
                            param_count += 1
                        elif operator == 'greaterThanOrEqual':
                            if column_id not in column_mapping:
                                column_conditions.append(f"({column_ref})::numeric >= ${param_count}::numeric")
                            else:
                                column_conditions.append(f"{column_ref} >= ${param_count}")
                            # Convert date strings for date columns
                            if column_id in ['created_at', 'created_date', 'updated_at', 'source_updated_at']:
                                params.append(parse_date_value(value))
                            else:
                                params.append(value)
                            param_count += 1
                        elif operator == 'lessThan':
                            if column_id not in column_mapping:
                                column_conditions.append(f"({column_ref})::numeric < ${param_count}::numeric")
                            else:
                                column_conditions.append(f"{column_ref} < ${param_count}")
                            # Convert date strings for date columns
                            if column_id in ['created_at', 'created_date', 'updated_at', 'source_updated_at']:
                                params.append(parse_date_value(value))
                            else:
                                params.append(value)
                            param_count += 1
                        elif operator == 'lessThanOrEqual':
                            if column_id not in column_mapping:
                                column_conditions.append(f"({column_ref})::numeric <= ${param_count}::numeric")
                            else:
                                column_conditions.append(f"{column_ref} <= ${param_count}")
                            # Convert date strings for date columns
                            if column_id in ['created_at', 'created_date', 'updated_at', 'source_updated_at']:
                                params.append(parse_date_value(value))
                            else:
                                params.append(value)
                            param_count += 1
                        elif operator == 'inRange':
                            if isinstance(value, list) and len(value) == 2:
                                if column_id not in column_mapping:
                                    column_conditions.append(f"({column_ref})::numeric BETWEEN ${param_count}::numeric AND ${param_count + 1}::numeric")
                                else:
                                    column_conditions.append(f"{column_ref} BETWEEN ${param_count} AND ${param_count + 1}")
                                # Convert date strings for date columns
                                if column_id in ['created_at', 'created_date', 'updated_at', 'source_updated_at']:
                                    params.extend([parse_date_value(value[0]), parse_date_value(value[1])])
                                else:
                                    params.extend([value[0], value[1]])
                                param_count += 2
                        elif operator in ['before', 'after', 'between']:
                            # Date operators
                            if operator == 'before':
                                if column_id not in column_mapping:
                                    column_conditions.append(f"({column_ref})::timestamp < ${param_count}::timestamp")
                                else:
                                    column_conditions.append(f"{column_ref} < ${param_count}::timestamp")
                                params.append(parse_date_value(value))
                                param_count += 1
                            elif operator == 'after':
                                if column_id not in column_mapping:
                                    column_conditions.append(f"({column_ref})::timestamp > ${param_count}::timestamp")
                                else:
                                    column_conditions.append(f"{column_ref} > ${param_count}::timestamp")
                                params.append(parse_date_value(value))
                                param_count += 1
                            elif operator == 'between' and isinstance(value, list) and len(value) == 2:
                                if column_id not in column_mapping:
                                    column_conditions.append(f"({column_ref})::timestamp BETWEEN ${param_count}::timestamp AND ${param_count + 1}::timestamp")
                                else:
                                    column_conditions.append(f"{column_ref} BETWEEN ${param_count}::timestamp AND ${param_count + 1}::timestamp")
                                params.extend([parse_date_value(value[0]), parse_date_value(value[1])])
                                param_count += 2
                    
                    if column_conditions:
                        if join_op == 'OR':
                            sql += f" AND ({' OR '.join(column_conditions)})"
                        else:
                            sql += f" AND ({' AND '.join(column_conditions)})"
    
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
    elif search_query.sort_by == "source":
        sql += f" ORDER BY source_name {search_query.sort_order.upper()}"
    elif search_query.sort_by == "source_category":
        sql += f" ORDER BY source_category {search_query.sort_order.upper()}"
    elif search_query.sort_by == "title":
        sql += f" ORDER BY title {search_query.sort_order.upper()}"
    elif search_query.sort_by == "created_date":
        sql += f""" ORDER BY CASE 
            WHEN source_category = 'community' THEN COALESCE((doc_metadata->>'posted_date')::timestamp, (doc_metadata->>'created_date')::timestamp)
            WHEN source_category = 'publications' THEN (doc_metadata->>'publication_date')::date
            WHEN source_category = 'trials' THEN COALESCE((doc_metadata->>'start_date')::date, (doc_metadata->>'study_start_date')::date)
            ELSE created_at
        END {search_query.sort_order.upper()}"""
    elif search_query.sort_by == "updated_at":
        sql += f" ORDER BY updated_at {search_query.sort_order.upper()}"
    elif search_query.sort_by == "source_updated_at":
        sql += f" ORDER BY COALESCE(source_updated_at, created_at) {search_query.sort_order.upper()}"
    elif search_query.sort_by and "." in search_query.sort_by:
        # Sort by metadata field
        json_path = "->".join([f"'{part}'" for part in search_query.sort_by.split(".")])
        sql += f" ORDER BY doc_metadata->{json_path} {search_query.sort_order.upper()}"
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


def generate_columns_for_results(results: List[UnifiedSearchResult], requested_categories: List[str] = None) -> List[Dict[str, Any]]:
    """Generate dynamic column configuration from actual result data"""
    
    # Base columns always shown
    columns = [
        {"key": "title", "label": "Title", "sortable": True, "width": "300", "frozen": True},
        {"key": "source", "label": "Source", "sortable": True, "width": "150", "frozen": True},
        {"key": "source_category", "label": "Type", "sortable": True, "width": "100", "render": "badge"},
        {"key": "created_date", "label": "Created", "sortable": True, "width": "120", "render": "date"},
        {"key": "source_updated_at", "label": "Last Activity", "sortable": True, "width": "120", "render": "date"},
        {"key": "updated_at", "label": "Scraped", "sortable": True, "width": "120", "render": "date"}
    ]
    
    # If no results, just return base columns
    if not results:
        return columns
    
    # Analyze metadata fields from actual results
    metadata_analysis = {}
    
    # Sample first 50 results or all if less
    sample_size = min(50, len(results))
    for result in results[:sample_size]:
        for field_name, value in result.metadata.items():
            if field_name not in metadata_analysis:
                metadata_analysis[field_name] = {
                    "count": 0,
                    "types": set(),
                    "non_null_count": 0,
                    "sample_values": [],
                    "max_length": 0,
                    "sources": set()
                }
            
            field_info = metadata_analysis[field_name]
            field_info["count"] += 1
            field_info["sources"].add(result.source_category)
            
            if value is not None:
                field_info["non_null_count"] += 1
                
                # Detect type
                if isinstance(value, list):
                    field_info["types"].add("list")
                    if len(field_info["sample_values"]) < 3:
                        field_info["sample_values"].append(len(value))
                elif isinstance(value, dict):
                    field_info["types"].add("dict")
                elif isinstance(value, bool):
                    field_info["types"].add("boolean")
                elif isinstance(value, (int, float)):
                    field_info["types"].add("number")
                elif isinstance(value, str):
                    field_info["types"].add("string")
                    field_info["max_length"] = max(field_info["max_length"], len(value))
                    # Check if it looks like a date
                    if any(pattern in value for pattern in ["-", "/", "T00:00:00"]) and len(value) <= 30:
                        field_info["types"].add("date")
    
    # Sort fields by frequency and name
    sorted_fields = sorted(
        metadata_analysis.items(),
        key=lambda x: (-x[1]["non_null_count"], x[0])
    )
    
    # Generate column configs for all metadata fields
    for field_name, field_info in sorted_fields:
        # Skip fields that are too sparse (less than 10% non-null)
        if field_info["non_null_count"] < sample_size * 0.1:
            continue
        
        # Skip redundant date fields for Reddit sources
        if field_name == "posted_date" and "community" in field_info["sources"]:
            # Skip this field as it's redundant with source_updated_at
            continue
            
        # Determine custom label based on field and source
        label = field_name.replace('_', ' ').title()
        
        # Custom labels for specific fields
        if field_name == "publication_date" and "publications" in field_info["sources"]:
            label = "Publication Date"
        elif field_name == "electronic_publication_date" and "publications" in field_info["sources"]:
            label = "Electronic Pub Date"
        elif field_name == "posted_date" and "community" in field_info["sources"]:
            label = "Posted"
        elif field_name == "last_update" and "trials" in field_info["sources"]:
            label = "Last Updated"
            
        col_config = {
            "key": f"metadata.{field_name}",
            "label": label,
            "sortable": False,
            "width": "150",
            "group": "metadata",
            "frequency": field_info["non_null_count"] / sample_size,
            "sources": list(field_info["sources"])
        }
        
        # Determine render type and width based on detected types
        types = field_info["types"]
        
        if "list" in types:
            col_config["render"] = "list"
            col_config["maxItems"] = 3
            # Set width based on average list length
            avg_length = sum(field_info["sample_values"]) / len(field_info["sample_values"]) if field_info["sample_values"] else 3
            col_config["width"] = "200" if avg_length > 2 else "150"
        elif "dict" in types:
            col_config["render"] = "json"
            col_config["width"] = "200"
        elif "boolean" in types:
            col_config["render"] = "boolean"
            col_config["width"] = "80"
        elif "number" in types:
            col_config["render"] = "number"
            col_config["width"] = "100"
        elif "date" in types or any(date_word in field_name.lower() for date_word in ["date", "time", "created", "updated", "received"]):
            col_config["render"] = "date"
            col_config["width"] = "120"
        elif field_name in ["status", "phase", "report_type", "category", "qualification"]:
            col_config["render"] = "badge"
            col_config["width"] = "120"
        elif field_name.endswith("_url") or field_name in ["doi", "url", "link"]:
            col_config["render"] = "link"
            col_config["width"] = "150"
        else:
            # String type - adjust width based on content
            if field_info["max_length"] > 100:
                col_config["width"] = "250"
            elif field_info["max_length"] > 50:
                col_config["width"] = "200"
            else:
                col_config["width"] = "150"
        
        columns.append(col_config)
    
    
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
        
        # Debug logging
        logger.info(f"SQL Query: {sql[:200]}...")
        logger.info(f"Parameters: {params}")
        logger.info(f"Parameter types: {[type(p).__name__ for p in params]}")
        
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
            
            
            # Extract created date based on source type
            created_date = None
            if metadata:
                if row['source_category'] == 'community':
                    # For Reddit, use posted_date (new) or created_date (legacy)
                    posted_date_str = metadata.get('posted_date') or metadata.get('created_date')
                    if posted_date_str:
                        try:
                            created_date = datetime.fromisoformat(posted_date_str.replace('Z', '+00:00'))
                        except:
                            pass
                elif row['source_category'] == 'publications':
                    # For PubMed, use publication_date
                    pub_date_str = metadata.get('publication_date')
                    if pub_date_str:
                        try:
                            created_date = datetime.strptime(pub_date_str, "%Y-%m-%d")
                        except:
                            pass
                elif row['source_category'] == 'trials':
                    # For ClinicalTrials, use start_date or study_start_date
                    start_date_str = metadata.get('start_date') or metadata.get('study_start_date')
                    if start_date_str:
                        try:
                            created_date = datetime.strptime(start_date_str, "%Y-%m-%d")
                        except:
                            pass
            
            # Fallback to created_at if no specific date found
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
        
        # Generate columns based on results and requested categories
        columns = generate_columns_for_results(search_results, search_query.source_categories)
        
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
    Enhanced field metadata endpoint for advanced query builder.
    Returns detailed field information including types, categories, operators, and sample values.
    """
    
    async with get_pg_connection() as conn:
        # Build source filter
        where_clause = "WHERE 1=1"
        and_conditions = ""
        params = []
        param_count = 1
        
        if source:
            where_clause += f" AND s.name = ${param_count}"
            and_conditions += f" AND s.name = ${param_count}"
            params.append(source)
            param_count += 1
        elif source_category:
            where_clause += f" AND s.category = ${param_count}"
            and_conditions += f" AND s.category = ${param_count}"
            params.append(source_category)
            param_count += 1
        
        # Sample from each source to capture all metadata schemas
        field_sql = f"""
            WITH source_samples AS (
                SELECT DISTINCT ON (s.name) 
                    d.doc_metadata,
                    s.category as source_category,
                    s.name as source_name
                FROM documents d
                JOIN sources s ON d.source_id = s.id
                WHERE d.doc_metadata IS NOT NULL
                {and_conditions}
                ORDER BY s.name, d.created_at DESC
            ),
            metadata_fields AS (
                SELECT DISTINCT 
                    jsonb_object_keys(doc_metadata) as field,
                    source_category,
                    source_name,
                    doc_metadata
                FROM source_samples
            )
            SELECT 
                field,
                COUNT(*) as doc_count,
                COUNT(DISTINCT source_category) as category_count,
                array_agg(DISTINCT source_category) as source_categories,
                'string' as field_type,
                COUNT(DISTINCT source_name) as unique_values
            FROM metadata_fields
            GROUP BY field
            ORDER BY doc_count DESC, field ASC
            LIMIT 100
        """
        
        fields = await conn.fetch(field_sql, *params)
        
        # Enhanced operator mappings
        operators = {
            "string": ["$eq", "$ne", "$contains", "$startsWith", "$endsWith", "$regex", "$in", "$nin", "$exists"],
            "number": ["$eq", "$ne", "$gt", "$gte", "$lt", "$lte", "$between", "$in", "$nin", "$exists"],
            "date": ["$eq", "$ne", "$gt", "$gte", "$lt", "$lte", "$between", "$exists"],
            "array": ["$contains", "$all", "$in", "$nin", "$exists"],
            "object": ["$exists"],
            "boolean": ["$eq", "$ne", "$exists"]
        }
        
        # Core fields that always appear first
        core_fields = ["_fulltext", "title", "source", "created_at", "updated_at", "source_updated_at", "summary", "url"]
        
        suggestions = {
            "fields": [],
            "operators": operators,
            "categories": {
                "core": "Core Fields",
                "publication": "Publication Data", 
                "trial": "Clinical Trial Data",
                "community": "Community Data",
                "faers": "Adverse Event Data",
                "dates": "Date Fields",
                "identifiers": "Identifiers",
                "other": "Other Fields"
            }
        }
        
        # Helper function to categorize fields
        def categorize_field(field_name: str, source_cats: list, field_type: str) -> str:
            field_lower = field_name.lower()
            
            # Core fields
            if field_name in core_fields:
                return "core"
            
            # Date fields
            if field_type == "date" or any(date_word in field_lower for date_word in 
                ["date", "time", "created", "updated", "received", "published", "start", "end"]):
                return "dates"
            
            # Identifiers
            if any(id_word in field_lower for id_word in 
                ["id", "pmid", "doi", "nct", "uuid", "identifier", "number"]):
                return "identifiers"
            
            # Source-specific categorization
            if len(source_cats) == 1:
                cat = source_cats[0]
                if cat == "publications":
                    return "publication"
                elif cat == "trials":
                    return "trial"
                elif cat == "community":
                    return "community"
                elif cat == "faers":
                    return "faers"
            
            return "other"
        
        # Helper function to generate field description
        def generate_description(field_name: str, field_type: str, doc_count: int, unique_values: int) -> str:
            base_name = field_name.replace('_', ' ').title()
            
            # Just return the base name without counts since we're sampling
            return base_name
        
        # Build enhanced field metadata
        for row in fields:
            field_name = row['field']
            field_type = row['field_type'] or 'string'
            doc_count = row['doc_count']
            unique_values = row['unique_values'] or 0
            source_categories = row['source_categories'] or []
            
            # Generate field metadata
            field_info = {
                "name": field_name,
                "label": field_name.replace('_', ' ').title(),
                "type": field_type,
                "category": categorize_field(field_name, source_categories, field_type),
                "description": generate_description(field_name, field_type, doc_count, unique_values),
                "document_count": doc_count,
                "unique_values": unique_values,
                "source_categories": source_categories if field_name not in core_fields else ['Common'],
                "operators": operators.get(field_type, ["$exists"])
            }
            
            # Get sample values for appropriate fields
            if field_type in ['string', 'number'] and unique_values <= 50 and doc_count >= 10:
                try:
                    sample_sql = f"""
                        SELECT DISTINCT doc_metadata->>'{field_name}' as value, COUNT(*) as count
                        FROM documents d
                        JOIN sources s ON d.source_id = s.id
                        WHERE doc_metadata->>'{field_name}' IS NOT NULL 
                        AND doc_metadata->>'{field_name}' != ''
                        {where_clause}
                        GROUP BY doc_metadata->>'{field_name}'
                        ORDER BY count DESC, value ASC
                        LIMIT 15
                    """
                    samples = await conn.fetch(sample_sql, *params)
                    field_info['sample_values'] = [
                        {"value": s['value'], "count": s['count']} 
                        for s in samples if s['value']
                    ]
                except Exception:
                    field_info['sample_values'] = []
            
            suggestions["fields"].append(field_info)
        
        # Add core document fields that might not be in metadata
        core_doc_fields = [
            {
                "name": "_fulltext",
                "label": "Full Text Search",
                "type": "string",
                "category": "core",
                "description": "Search across title, content, and summary",
                "operators": ["$contains"],
                "source_categories": ['Common']
            },
            {
                "name": "title",
                "label": "Title", 
                "type": "string",
                "category": "core",
                "description": "Document title",
                "operators": operators["string"],
                "source_categories": ['Common']
            },
            {
                "name": "source",
                "label": "Source",
                "type": "string", 
                "category": "core",
                "description": "Data source name",
                "operators": operators["string"],
                "source_categories": ['Common']
            },
            {
                "name": "created_at",
                "label": "Scraped Date",
                "type": "date",
                "category": "dates", 
                "description": "Date when document was scraped/collected",
                "operators": operators["date"],
                "source_categories": ['Common']
            },
            {
                "name": "updated_at",
                "label": "Last Updated",
                "type": "date",
                "category": "dates",
                "description": "Date when document was last updated in our database",
                "operators": operators["date"],
                "source_categories": ['Common']
            },
            {
                "name": "source_updated_at",
                "label": "Source Date",
                "type": "date",
                "category": "dates",
                "description": "Date when the source indicates the document was last modified",
                "operators": operators["date"],
                "source_categories": ['Common']
            },
            {
                "name": "summary",
                "label": "Summary",
                "type": "string",
                "category": "core",
                "description": "Document summary",
                "operators": operators["string"],
                "source_categories": ['Common']
            },
            {
                "name": "url",
                "label": "URL",
                "type": "string",
                "category": "core",
                "description": "Source URL",
                "operators": operators["string"],
                "source_categories": ['Common']
            }
        ]
        
        # Add core fields if not already present
        existing_field_names = {f["name"] for f in suggestions["fields"]}
        for core_field in core_doc_fields:
            if core_field["name"] not in existing_field_names:
                suggestions["fields"].insert(0, core_field)
        
        # Sort fields: core first, then by category and frequency
        category_order = ["core", "dates", "identifiers", "publication", "trial", "community", "faers", "other"]
        
        def sort_key(field):
            cat_idx = category_order.index(field.get("category", "other"))
            doc_count = field.get("document_count", 0)
            return (cat_idx, -doc_count, field["name"])
        
        suggestions["fields"].sort(key=sort_key)
        
        return suggestions


@router.get("/unified/export")
async def export_unified_search(
    format: str = "json",
    q: Optional[str] = None,
    sources: Optional[List[str]] = None,
    source_categories: Optional[List[str]] = None,
    diseases: Optional[List[str]] = None,
    limit: int = 10000  # Export all results by default
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