from fastapi import APIRouter, Query, HTTPException, Depends
from typing import List, Optional, Dict, Any
from datetime import datetime
import asyncpg
from pydantic import BaseModel, Field
import numpy as np
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
import time
import json

from core.database import get_db, get_pg_connection
from core.config import settings
from models.database import Document, Source, Disease, DocumentDisease
from models.schemas import SearchResult, SearchResponse, DocumentDetail, SourceType

router = APIRouter(prefix="/api/search", tags=["search"])


class EnhancedSearchQuery(BaseModel):
    """Enhanced search query with complex filtering support"""
    q: str = Field(..., description="Search query text")
    
    # Basic filters
    diseases: Optional[List[str]] = Field(None, description="Filter by disease names")
    sources: Optional[List[str]] = Field(None, description="Filter by source names")
    source_types: Optional[List[SourceType]] = Field(None, description="Filter by source types (primary/secondary)")
    
    # Date filters
    date_from: Optional[datetime] = Field(None, description="Filter by document creation date (from)")
    date_to: Optional[datetime] = Field(None, description="Filter by document creation date (to)")
    publication_date_from: Optional[datetime] = Field(None, description="Filter by publication date (from)")
    publication_date_to: Optional[datetime] = Field(None, description="Filter by publication date (to)")
    
    # Clinical trials specific filters
    study_phases: Optional[List[str]] = Field(None, description="Filter by clinical trial phases")
    study_types: Optional[List[str]] = Field(None, description="Filter by clinical trial study types")
    trial_status: Optional[List[str]] = Field(None, description="Filter by clinical trial status")
    
    # PubMed specific filters
    publication_types: Optional[List[str]] = Field(None, description="Filter by PubMed publication types")
    journals: Optional[List[str]] = Field(None, description="Filter by journal names")
    mesh_terms: Optional[List[str]] = Field(None, description="Filter by MeSH terms")
    
    # Search configuration
    search_type: str = Field("keyword", description="Search type: keyword, semantic, or hybrid")
    limit: int = Field(50, le=100, description="Maximum results to return")
    offset: int = Field(0, ge=0, description="Offset for pagination")
    
    # Hybrid search weight
    keyword_weight: float = Field(0.5, ge=0, le=1, description="Weight for keyword search in hybrid mode")


class FilterOptions(BaseModel):
    """Available filter options with counts"""
    sources: List[Dict[str, Any]]
    source_types: List[Dict[str, Any]]
    diseases: List[Dict[str, Any]]
    study_phases: List[Dict[str, Any]]
    study_types: List[Dict[str, Any]]
    trial_statuses: List[Dict[str, Any]]
    publication_types: List[Dict[str, Any]]
    journals: List[Dict[str, Any]]
    date_ranges: Dict[str, Any]


async def build_complex_filters(
    db: AsyncSession,
    search_query: EnhancedSearchQuery
) -> Dict[str, Any]:
    """Build complex filters from search query"""
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
    
    # Filter by source types
    if search_query.source_types:
        type_result = await db.execute(
            text("SELECT id FROM sources WHERE type = ANY(:types)"),
            {"types": search_query.source_types}
        )
        type_ids = [row[0] for row in type_result]
        if type_ids:
            if 'source_ids' in filters:
                # Intersection of source filters
                filters['source_ids'] = list(set(filters['source_ids']) & set(type_ids))
            else:
                filters['source_ids'] = type_ids
    
    # Convert disease names to IDs
    if search_query.diseases:
        disease_result = await db.execute(
            text("SELECT id FROM diseases WHERE name = ANY(:diseases)"),
            {"diseases": search_query.diseases}
        )
        disease_ids = [row[0] for row in disease_result]
        if disease_ids:
            filters['disease_ids'] = disease_ids
    
    # Date filters
    if search_query.date_from:
        filters['date_from'] = search_query.date_from
    if search_query.date_to:
        filters['date_to'] = search_query.date_to
    if search_query.publication_date_from:
        filters['publication_date_from'] = search_query.publication_date_from
    if search_query.publication_date_to:
        filters['publication_date_to'] = search_query.publication_date_to
    
    # Clinical trials filters
    if search_query.study_phases:
        filters['study_phases'] = search_query.study_phases
    if search_query.study_types:
        filters['study_types'] = search_query.study_types
    if search_query.trial_status:
        filters['trial_status'] = search_query.trial_status
    
    # PubMed filters
    if search_query.publication_types:
        filters['publication_types'] = search_query.publication_types
    if search_query.journals:
        filters['journals'] = search_query.journals
    if search_query.mesh_terms:
        filters['mesh_terms'] = search_query.mesh_terms
    
    return filters


def add_metadata_filters(sql: str, filters: Dict[str, Any], param_count: int) -> tuple[str, list, int]:
    """Add metadata-based filters to SQL query"""
    params = []
    
    # Clinical trials filters
    if filters.get('study_phases'):
        sql += f" AND d.metadata->'phase' ?| ${param_count}"
        params.append(filters['study_phases'])
        param_count += 1
    
    if filters.get('study_types'):
        sql += f" AND d.metadata->>'study_type' = ANY(${param_count})"
        params.append(filters['study_types'])
        param_count += 1
    
    if filters.get('trial_status'):
        sql += f" AND d.metadata->>'status' = ANY(${param_count})"
        params.append(filters['trial_status'])
        param_count += 1
    
    # PubMed filters
    if filters.get('publication_types'):
        sql += f" AND d.metadata->'article_types' ?| ${param_count}"
        params.append(filters['publication_types'])
        param_count += 1
    
    if filters.get('journals'):
        sql += f" AND d.metadata->>'journal' = ANY(${param_count})"
        params.append(filters['journals'])
        param_count += 1
    
    if filters.get('mesh_terms'):
        sql += f" AND d.metadata->'mesh_terms' ?| ${param_count}"
        params.append(filters['mesh_terms'])
        param_count += 1
    
    # Publication date filters (handle different date formats)
    if filters.get('publication_date_from') or filters.get('publication_date_to'):
        date_condition = """
            AND (
                -- ClinicalTrials.gov start date
                (d.metadata->>'start_date' IS NOT NULL AND 
                 d.metadata->>'start_date'::date BETWEEN COALESCE($%s, '1900-01-01'::date) AND COALESCE($%s, '2100-01-01'::date))
                OR
                -- PubMed publication date
                (d.metadata->'publication_dates'->>'pubmed' IS NOT NULL AND 
                 (d.metadata->'publication_dates'->>'pubmed')::date BETWEEN COALESCE($%s, '1900-01-01'::date) AND COALESCE($%s, '2100-01-01'::date))
            )
        """
        sql += date_condition % (param_count, param_count + 1, param_count, param_count + 1)
        params.extend([
            filters.get('publication_date_from'),
            filters.get('publication_date_to')
        ])
        param_count += 2
    
    return sql, params, param_count


async def perform_enhanced_keyword_search(
    conn: asyncpg.Connection,
    query: str,
    filters: Dict[str, Any],
    limit: int,
    offset: int
) -> List[asyncpg.Record]:
    """Enhanced keyword search with complex filtering"""
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
    
    # Basic filters
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
    
    # Add metadata filters
    sql, metadata_params, param_count = add_metadata_filters(sql, filters, param_count)
    params.extend(metadata_params)
    
    # Add ordering and pagination
    sql += f" ORDER BY rank DESC LIMIT ${param_count} OFFSET ${param_count + 1}"
    params.extend([limit, offset])
    
    return await conn.fetch(sql, *params)


@router.post("/enhanced", response_model=SearchResponse)
async def enhanced_search(
    search_query: EnhancedSearchQuery,
    db: AsyncSession = Depends(get_db)
):
    """
    Enhanced search with complex filtering capabilities.
    
    Supports filtering by:
    - Source types (primary/secondary)
    - Clinical trial phases, types, and status
    - PubMed publication types, journals, and MeSH terms
    - Publication dates (in addition to system dates)
    """
    start_time = time.time()
    
    try:
        # Build filters
        filters = await build_complex_filters(db, search_query)
        
        # Use async context manager for pg connection
        async with get_pg_connection() as conn:
            # Perform search based on type
            if search_query.search_type == "keyword":
                results = await perform_enhanced_keyword_search(
                    conn, search_query.q, filters, search_query.limit, search_query.offset
                )
            else:
                # For now, fall back to basic search for semantic/hybrid
                # TODO: Implement enhanced semantic and hybrid search
                results = await perform_enhanced_keyword_search(
                    conn, search_query.q, filters, search_query.limit, search_query.offset
                )
            
            # Count total results
            count_sql = """
                SELECT COUNT(DISTINCT d.id)
                FROM documents d
                JOIN sources s ON d.source_id = s.id
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
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/filters/enhanced", response_model=FilterOptions)
async def get_enhanced_filter_options(db: AsyncSession = Depends(get_db)):
    """Get available filter options with counts for the enhanced search interface"""
    
    try:
        async with get_pg_connection() as conn:
            # Get sources with counts
            sources_sql = """
                SELECT s.name, s.type, COUNT(d.id) as document_count
                FROM sources s
                LEFT JOIN documents d ON s.id = d.source_id
                WHERE s.is_active = true
                GROUP BY s.id, s.name, s.type
                ORDER BY document_count DESC
            """
            sources = await conn.fetch(sources_sql)
            
            # Get source types with counts
            source_types_sql = """
                SELECT s.type, COUNT(DISTINCT d.id) as document_count
                FROM sources s
                JOIN documents d ON s.id = d.source_id
                WHERE s.is_active = true
                GROUP BY s.type
            """
            source_types = await conn.fetch(source_types_sql)
            
            # Get diseases with counts
            diseases_sql = """
                SELECT dis.name, COUNT(DISTINCT dd.document_id) as document_count
                FROM diseases dis
                JOIN document_diseases dd ON dis.id = dd.disease_id
                GROUP BY dis.id, dis.name
                ORDER BY document_count DESC
                LIMIT 50
            """
            diseases = await conn.fetch(diseases_sql)
            
            # Get clinical trial phases
            phases_sql = """
                SELECT DISTINCT jsonb_array_elements_text(metadata->'phase') as phase,
                       COUNT(*) as count
                FROM documents
                WHERE metadata->'phase' IS NOT NULL
                GROUP BY phase
                ORDER BY count DESC
            """
            phases = await conn.fetch(phases_sql)
            
            # Get study types
            study_types_sql = """
                SELECT DISTINCT metadata->>'study_type' as study_type,
                       COUNT(*) as count
                FROM documents
                WHERE metadata->>'study_type' IS NOT NULL
                GROUP BY study_type
                ORDER BY count DESC
            """
            study_types = await conn.fetch(study_types_sql)
            
            # Get trial statuses
            statuses_sql = """
                SELECT DISTINCT metadata->>'status' as status,
                       COUNT(*) as count
                FROM documents
                WHERE metadata->>'status' IS NOT NULL
                GROUP BY status
                ORDER BY count DESC
            """
            statuses = await conn.fetch(statuses_sql)
            
            # Get publication types
            pub_types_sql = """
                SELECT DISTINCT jsonb_array_elements_text(metadata->'article_types') as pub_type,
                       COUNT(*) as count
                FROM documents
                WHERE metadata->'article_types' IS NOT NULL
                GROUP BY pub_type
                ORDER BY count DESC
                LIMIT 20
            """
            pub_types = await conn.fetch(pub_types_sql)
            
            # Get journals
            journals_sql = """
                SELECT DISTINCT metadata->>'journal' as journal,
                       COUNT(*) as count
                FROM documents
                WHERE metadata->>'journal' IS NOT NULL
                GROUP BY journal
                ORDER BY count DESC
                LIMIT 20
            """
            journals = await conn.fetch(journals_sql)
            
            # Get date ranges
            date_ranges_sql = """
                SELECT 
                    MIN(created_at) as min_created_date,
                    MAX(created_at) as max_created_date,
                    MIN(CASE 
                        WHEN metadata->>'start_date' IS NOT NULL 
                        THEN (metadata->>'start_date')::date 
                        ELSE NULL 
                    END) as min_publication_date,
                    MAX(CASE 
                        WHEN metadata->>'start_date' IS NOT NULL 
                        THEN (metadata->>'start_date')::date 
                        ELSE NULL 
                    END) as max_publication_date
                FROM documents
            """
            date_ranges = await conn.fetchrow(date_ranges_sql)
        
        return FilterOptions(
            sources=[{"name": r['name'], "type": r['type'], "count": r['document_count']} for r in sources],
            source_types=[{"type": r['type'], "count": r['document_count']} for r in source_types],
            diseases=[{"name": r['name'], "count": r['document_count']} for r in diseases],
            study_phases=[{"value": r['phase'], "count": r['count']} for r in phases if r['phase']],
            study_types=[{"value": r['study_type'], "count": r['count']} for r in study_types if r['study_type']],
            trial_statuses=[{"value": r['status'], "count": r['count']} for r in statuses if r['status']],
            publication_types=[{"value": r['pub_type'], "count": r['count']} for r in pub_types if r['pub_type']],
            journals=[{"value": r['journal'], "count": r['count']} for r in journals if r['journal']],
            date_ranges={
                "min_created_date": date_ranges['min_created_date'].isoformat() if date_ranges['min_created_date'] else None,
                "max_created_date": date_ranges['max_created_date'].isoformat() if date_ranges['max_created_date'] else None,
                "min_publication_date": date_ranges['min_publication_date'].isoformat() if date_ranges['min_publication_date'] else None,
                "max_publication_date": date_ranges['max_publication_date'].isoformat() if date_ranges['max_publication_date'] else None,
            }
        )
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))