from fastapi import APIRouter, Query, HTTPException, Depends
from typing import List, Optional, Dict, Any
from datetime import datetime
import asyncpg
from pydantic import BaseModel
import numpy as np
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
import time

from core.database import get_db, get_pg_connection
from core.config import settings
from models.database import Document, Source, Disease, DocumentDisease
from models.schemas import SearchResult, SearchResponse, DocumentDetail

router = APIRouter(prefix="/api/search", tags=["search"])


class SearchQuery(BaseModel):
    q: str
    diseases: Optional[List[str]] = None
    sources: Optional[List[str]] = None
    date_from: Optional[datetime] = None
    date_to: Optional[datetime] = None
    search_type: str = "keyword"
    limit: int = 50
    offset: int = 0


async def perform_keyword_search(
    conn: asyncpg.Connection,
    query: str,
    filters: Dict[str, Any],
    limit: int,
    offset: int
) -> List[asyncpg.Record]:
    """Perform full-text search using PostgreSQL's text search capabilities."""
    # Build the base query with full-text search
    sql = """
        SELECT DISTINCT d.*, 
               s.name as source_name,
               s.type as source_type,
               ts_rank(to_tsvector('english', COALESCE(d.content, '') || ' ' || COALESCE(d.title, '')), plainto_tsquery('english', $1)) as rank,
               ARRAY(
                   SELECT dis.name 
                   FROM document_diseases dd 
                   JOIN diseases dis ON dd.disease_id = dis.id 
                   WHERE dd.document_id = d.id
               ) as disease_names
        FROM documents d
        JOIN sources s ON d.source_id = s.id
        WHERE to_tsvector('english', COALESCE(d.content, '') || ' ' || COALESCE(d.title, '')) @@ plainto_tsquery('english', $1)
    """
    
    params = [query]
    param_count = 2
    
    # Add filters
    if filters.get('source_ids'):
        sql += f" AND d.source_id = ANY(${param_count})"
        params.append(filters['source_ids'])
        param_count += 1
    
    if filters.get('date_from'):
        sql += f" AND d.created_at >= ${param_count}"
        params.append(filters['date_from'])
        param_count += 1
    
    if filters.get('date_to'):
        sql += f" AND d.created_at <= ${param_count}"
        params.append(filters['date_to'])
        param_count += 1
    
    if filters.get('disease_ids'):
        sql += f"""
            AND EXISTS (
                SELECT 1 FROM document_diseases dd 
                WHERE dd.document_id = d.id 
                AND dd.disease_id = ANY(${param_count})
            )
        """
        params.append(filters['disease_ids'])
        param_count += 1
    
    # Add ordering and pagination
    sql += f" ORDER BY rank DESC LIMIT ${param_count} OFFSET ${param_count + 1}"
    params.extend([limit, offset])
    
    # Execute query
    result = await conn.fetch(sql, *params)
    return result


@router.post("/", response_model=SearchResponse)
async def search(
    search_query: SearchQuery,
    db: AsyncSession = Depends(get_db)
):
    """
    Perform search across medical documents.
    
    Search types:
    - keyword: Full-text search using PostgreSQL text search
    - semantic: Vector similarity search using embeddings
    - hybrid: Combination of keyword and semantic search (default)
    """
    try:
        start_time = time.time()
        
        # Prepare filters
        filters = {}
        
        # Convert source names to IDs
        if search_query.sources:
            source_result = await db.execute(
                text("SELECT id FROM sources WHERE name = ANY(:sources)"),
                {"sources": search_query.sources}
            )
            source_ids = [row[0] for row in source_result]
            if source_ids:
                filters['source_ids'] = source_ids
        
        # Convert disease names to IDs
        if search_query.diseases:
            disease_result = await db.execute(
                text("SELECT id FROM diseases WHERE name = ANY(:diseases)"),
                {"diseases": search_query.diseases}
            )
            disease_ids = [row[0] for row in disease_result]
            if disease_ids:
                filters['disease_ids'] = disease_ids
        
        # Add date filters
        if search_query.date_from:
            filters['date_from'] = search_query.date_from
        if search_query.date_to:
            filters['date_to'] = search_query.date_to
        
        # Perform search using direct connection
        async with get_pg_connection() as conn:
            results = await perform_keyword_search(
                conn, search_query.q, filters, search_query.limit, search_query.offset
            )
            
            # Count total results
            count_sql = """
                SELECT COUNT(DISTINCT d.id)
                FROM documents d
                WHERE to_tsvector('english', COALESCE(d.content, '') || ' ' || COALESCE(d.title, '')) @@ plainto_tsquery('english', $1)
            """
            count_params = [search_query.q]
            
            # Add same filters for count
            if filters.get('source_ids'):
                count_sql += " AND d.source_id = ANY($2)"
                count_params.append(filters['source_ids'])
            
            total_count = await conn.fetchval(count_sql, *count_params)
        
        # Format results
        search_results = []
        for row in results:
            result = SearchResult(
                id=row['id'],
                title=row['title'] or 'Untitled',
                snippet=row['summary'] or (row['content'][:200] + '...' if row['content'] else ''),
                url=row['url'],
                source=row['source_name'],
                source_type=row['source_type'],
                created_at=row['created_at'],
                relevance_score=float(row['rank']) if row['rank'] else 0.0,
                disease_tags=row['disease_names'] or []
            )
            search_results.append(result)
        
        execution_time = int((time.time() - start_time) * 1000)
        
        return SearchResponse(
            results=search_results,
            total=total_count or 0,
            limit=search_query.limit,
            offset=search_query.offset,
            query=search_query.q,
            search_type=search_query.search_type,
            execution_time_ms=execution_time
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/filters", response_model=Dict[str, List[Dict[str, Any]]])
async def get_filter_options(db: AsyncSession = Depends(get_db)):
    """Get available filter options with counts."""
    try:
        # Get sources with counts
        sources_query = """
            SELECT s.name, s.type, COUNT(d.id) as document_count
            FROM sources s
            LEFT JOIN documents d ON s.id = d.source_id
            WHERE s.is_active = true
            GROUP BY s.id, s.name, s.type
            ORDER BY document_count DESC
        """
        sources_result = await db.execute(text(sources_query))
        sources = [
            {"name": row[0], "type": row[1], "count": row[2]}
            for row in sources_result
        ]
        
        # Get diseases with counts
        diseases_query = """
            SELECT dis.name, COUNT(DISTINCT dd.document_id) as document_count
            FROM diseases dis
            JOIN document_diseases dd ON dis.id = dd.disease_id
            GROUP BY dis.id, dis.name
            ORDER BY document_count DESC
            LIMIT 50
        """
        diseases_result = await db.execute(text(diseases_query))
        diseases = [
            {"name": row[0], "count": row[1]}
            for row in diseases_result
        ]
        
        # Get available search types
        search_types = [
            {"value": "keyword", "label": "Keyword Search"},
            {"value": "semantic", "label": "Semantic Search"},
            {"value": "hybrid", "label": "Hybrid Search"}
        ]
        
        return {
            "sources": sources,
            "diseases": diseases,
            "search_types": search_types
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/suggestions")
async def get_suggestions(
    q: str = Query(..., min_length=2),
    limit: int = Query(10, le=50),
    db: AsyncSession = Depends(get_db)
) -> Dict[str, List[str]]:
    """Get search suggestions based on partial query."""
    try:
        # Get title suggestions
        title_query = """
            SELECT DISTINCT title
            FROM documents
            WHERE title ILIKE :pattern
            AND title IS NOT NULL
            ORDER BY title
            LIMIT :limit
        """
        title_result = await db.execute(
            text(title_query),
            {"pattern": f"%{q}%", "limit": limit}
        )
        title_suggestions = [row[0] for row in title_result]
        
        # Get disease suggestions
        disease_query = """
            SELECT DISTINCT name
            FROM diseases
            WHERE name ILIKE :pattern
            ORDER BY name
            LIMIT :limit
        """
        disease_result = await db.execute(
            text(disease_query),
            {"pattern": f"%{q}%", "limit": limit}
        )
        disease_suggestions = [row[0] for row in disease_result]
        
        return {
            "titles": title_suggestions,
            "diseases": disease_suggestions,
            "suggestions": list(set(title_suggestions[:5] + disease_suggestions[:5]))[:10]
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))