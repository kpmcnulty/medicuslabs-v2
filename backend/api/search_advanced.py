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


class AdvancedSearchQuery(BaseModel):
    """Advanced search with dynamic field support"""
    q: Optional[str] = Field(None, description="Search query text")
    source_types: Optional[List[str]] = Field(None, description="Filter by source types")
    disease: Optional[str] = Field(None, description="Filter by disease name")
    metadata_filters: Optional[Dict[str, Any]] = Field(None, description="Dynamic metadata filters")
    return_fields: Optional[List[str]] = Field(None, description="Fields to return")
    dynamic_columns: bool = Field(True, description="Return columns based on source type")
    limit: int = Field(50, le=100)
    offset: int = Field(0, ge=0)


class DynamicSearchResult(BaseModel):
    """Search result with dynamic fields"""
    id: int
    title: str
    url: str
    source: str
    source_type: str
    created_at: datetime
    relevance_score: float
    # Core fields
    summary: Optional[str] = None
    content_snippet: Optional[str] = None
    # Dynamic metadata fields
    metadata: Dict[str, Any] = {}
    # Display configuration
    display_fields: List[str] = []


class DynamicSearchResponse(BaseModel):
    """Response with dynamic column configuration"""
    results: List[DynamicSearchResult]
    total: int
    limit: int
    offset: int
    query: Optional[str]
    execution_time_ms: int
    # Column configuration for UI
    columns: List[Dict[str, Any]]
    source_breakdown: Dict[str, int]


# Column configurations for each source type
COLUMN_CONFIGS = {
    "PubMed": [
        {"key": "title", "label": "Title", "type": "string", "width": "30%"},
        {"key": "metadata.journal", "label": "Journal", "type": "string", "width": "15%"},
        {"key": "metadata.authors", "label": "Authors", "type": "array", "width": "20%", "render": "first_three"},
        {"key": "metadata.publication_date", "label": "Pub Date", "type": "date", "width": "10%"},
        {"key": "metadata.pmid", "label": "PMID", "type": "string", "width": "10%"},
        {"key": "metadata.article_types", "label": "Type", "type": "array", "width": "15%", "render": "tags"}
    ],
    "ClinicalTrials.gov": [
        {"key": "title", "label": "Title", "type": "string", "width": "35%"},
        {"key": "metadata.nct_id", "label": "NCT ID", "type": "string", "width": "10%"},
        {"key": "metadata.status", "label": "Status", "type": "string", "width": "10%", "render": "status_badge"},
        {"key": "metadata.phase", "label": "Phase", "type": "array", "width": "10%", "render": "tags"},
        {"key": "metadata.conditions", "label": "Conditions", "type": "array", "width": "20%", "render": "tags"},
        {"key": "metadata.start_date", "label": "Start Date", "type": "date", "width": "15%"}
    ],
    "secondary": [
        {"key": "title", "label": "Title", "type": "string", "width": "40%"},
        {"key": "source", "label": "Source", "type": "string", "width": "15%"},
        {"key": "metadata.author", "label": "Author", "type": "string", "width": "15%"},
        {"key": "metadata.posted_date", "label": "Posted", "type": "date", "width": "15%"},
        {"key": "metadata.engagement", "label": "Engagement", "type": "object", "width": "15%", "render": "engagement_stats"}
    ]
}


async def build_dynamic_query(
    conn: asyncpg.Connection,
    search_query: AdvancedSearchQuery
) -> tuple[str, list]:
    """Build dynamic SQL query based on search parameters"""
    
    # Base query with metadata
    sql = """
        SELECT DISTINCT 
            d.id,
            d.title,
            d.url,
            d.summary,
            d.content,
            d.created_at,
            d.metadata,
            s.name as source_name,
            s.type as source_type
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
    
    # Add text search condition
    if search_query.q:
        sql += f" AND to_tsvector('english', COALESCE(d.content, '') || ' ' || COALESCE(d.title, '')) @@ plainto_tsquery('english', ${param_count})"
        params.append(search_query.q)
        param_count += 1
    
    # Filter by source types
    if search_query.source_types:
        # Map source type IDs to actual source names
        source_mapping = {
            'publications': ['PubMed'],
            'trials': ['ClinicalTrials.gov'],
            'secondary': ['Reddit Medical', 'HealthUnlocked', 'Patient.info Forums']
        }
        
        source_names = []
        for st in search_query.source_types:
            if st in source_mapping:
                source_names.extend(source_mapping[st])
            else:
                source_names.append(st)
        
        sql += f" AND s.name = ANY(${param_count})"
        params.append(source_names)
        param_count += 1
    
    # Filter by disease
    if search_query.disease:
        sql += f""" AND EXISTS (
            SELECT 1 FROM document_diseases dd
            JOIN diseases dis ON dd.disease_id = dis.id
            WHERE dd.document_id = d.id
            AND dis.name = ${param_count}
        )"""
        params.append(search_query.disease)
        param_count += 1
    
    # Add metadata filters
    if search_query.metadata_filters:
        for field, value in search_query.metadata_filters.items():
            field_path = field.replace('metadata.', '')
            
            if isinstance(value, list):
                # Array contains any
                sql += f" AND d.metadata->'{field_path}' ?| ${param_count}"
                params.append(value)
                param_count += 1
            elif isinstance(value, dict) and 'min' in value or 'max' in value:
                # Range query
                if 'min' in value:
                    sql += f" AND (d.metadata->>'{field_path}')::date >= ${param_count}"
                    params.append(value['min'])
                    param_count += 1
                if 'max' in value:
                    sql += f" AND (d.metadata->>'{field_path}')::date <= ${param_count}"
                    params.append(value['max'])
                    param_count += 1
            else:
                # Exact match
                sql += f" AND d.metadata->>'{field_path}' = ${param_count}"
                params.append(str(value))
                param_count += 1
    
    # Order and pagination
    sql += f" ORDER BY rank DESC, d.created_at DESC LIMIT ${param_count} OFFSET ${param_count + 1}"
    params.extend([search_query.limit, search_query.offset])
    
    return sql, params


def get_dynamic_columns(source_types: List[str]) -> List[Dict[str, Any]]:
    """Get column configuration based on source types"""
    if not source_types:
        # Default columns for all sources
        return [
            {"key": "title", "label": "Title", "type": "string", "width": "40%"},
            {"key": "source", "label": "Source", "type": "string", "width": "15%"},
            {"key": "summary", "label": "Summary", "type": "string", "width": "35%"},
            {"key": "created_at", "label": "Added", "type": "date", "width": "10%"}
        ]
    
    # If single source type, use specific columns
    if len(source_types) == 1:
        source_type = source_types[0]
        
        # Map source type to configuration
        if source_type == 'publications':
            return COLUMN_CONFIGS["PubMed"]
        elif source_type == 'trials':
            return COLUMN_CONFIGS["ClinicalTrials.gov"]
        elif source_type == 'secondary':
            return COLUMN_CONFIGS["secondary"]
    
    # Mixed sources - use common columns plus source indicator
    return [
        {"key": "title", "label": "Title", "type": "string", "width": "35%"},
        {"key": "source", "label": "Source", "type": "string", "width": "15%"},
        {"key": "source_type", "label": "Type", "type": "string", "width": "10%", "render": "badge"},
        {"key": "summary", "label": "Summary", "type": "string", "width": "30%"},
        {"key": "created_at", "label": "Added", "type": "date", "width": "10%"}
    ]


def extract_display_fields(doc: dict, columns: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Extract fields for display based on column configuration"""
    display_data = {}
    
    for col in columns:
        key = col["key"]
        
        if "." in key:
            # Handle nested fields
            parts = key.split(".")
            value = doc
            for part in parts:
                if isinstance(value, dict) and part in value:
                    value = value[part]
                else:
                    value = None
                    break
            display_data[key] = value
        else:
            # Direct field
            display_data[key] = doc.get(key)
    
    return display_data


@router.post("/advanced", response_model=DynamicSearchResponse)
async def advanced_search(search_query: AdvancedSearchQuery):
    """
    Advanced search with dynamic columns based on source type.
    
    Returns results with columns configured for the selected source types.
    """
    start_time = time.time()
    
    async with get_pg_connection() as conn:
        # Build and execute search query
        sql, params = await build_dynamic_query(conn, search_query)
        results = await conn.fetch(sql, *params)
        
        # Get total count
        count_sql = sql.split("ORDER BY")[0].replace("SELECT DISTINCT d.*, s.name as source_name, s.type as source_type", "SELECT COUNT(DISTINCT d.id)")
        count_result = await conn.fetchval(count_sql, *params[:-2])  # Exclude limit/offset
        
        # Get column configuration
        columns = get_dynamic_columns(search_query.source_types or [])
        
        # Process results
        search_results = []
        source_breakdown = {}
        
        for row in results:
            # Track source breakdown
            source_name = row['source_name']
            source_breakdown[source_name] = source_breakdown.get(source_name, 0) + 1
            
            # Parse metadata
            metadata = json.loads(row['metadata']) if row['metadata'] else {}
            
            # Create result object
            doc_data = {
                "id": row["id"],
                "title": row["title"],
                "url": row["url"],
                "source": source_name,
                "source_type": row["source_type"],
                "created_at": row["created_at"],
                "summary": row["summary"],
                "metadata": metadata
            }
            
            # Extract display fields based on columns
            display_metadata = extract_display_fields(doc_data, columns)
            
            result = DynamicSearchResult(
                id=row['id'],
                title=row['title'] or 'Untitled',
                url=row['url'],
                source=source_name,
                source_type=row['source_type'],
                created_at=row['created_at'],
                relevance_score=float(row['rank']) if row.get('rank') else 1.0,
                summary=row['summary'],
                content_snippet=(row['content'][:200] + '...') if row['content'] else None,
                metadata=display_metadata,
                display_fields=list(display_metadata.keys())
            )
            
            search_results.append(result)
        
        execution_time = int((time.time() - start_time) * 1000)
        
        return DynamicSearchResponse(
            results=search_results,
            total=count_result or 0,
            limit=search_query.limit,
            offset=search_query.offset,
            query=search_query.q,
            execution_time_ms=execution_time,
            columns=columns,
            source_breakdown=source_breakdown
        )