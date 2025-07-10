from fastapi import APIRouter, HTTPException, Depends
from typing import List, Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text

from core.database import get_db, get_pg_connection

router = APIRouter(prefix="/api/search", tags=["search"])


@router.get("/filters/enhanced")
async def get_enhanced_filter_options():
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
                LEFT JOIN documents d ON s.id = d.source_id
                WHERE s.is_active = true
                GROUP BY s.type
                ORDER BY document_count DESC
            """
            source_types = await conn.fetch(source_types_sql)
            
            # Get diseases with counts
            diseases_sql = """
                SELECT dis.name, COUNT(DISTINCT dd.document_id) as document_count
                FROM diseases dis
                LEFT JOIN document_diseases dd ON dis.id = dd.disease_id
                GROUP BY dis.id, dis.name
                ORDER BY document_count DESC
                LIMIT 50
            """
            diseases = await conn.fetch(diseases_sql)
            
            # Get clinical trial phases - Fixed query
            phases_sql = """
                WITH phase_data AS (
                    SELECT jsonb_array_elements_text(metadata->'phase') as phase
                    FROM documents
                    WHERE metadata->'phase' IS NOT NULL
                    AND jsonb_typeof(metadata->'phase') = 'array'
                )
                SELECT phase, COUNT(*) as count
                FROM phase_data
                WHERE phase IS NOT NULL
                GROUP BY phase
                ORDER BY count DESC
            """
            phases = await conn.fetch(phases_sql)
            
            # Get study types
            study_types_sql = """
                SELECT metadata->>'study_type' as study_type,
                       COUNT(*) as count
                FROM documents
                WHERE metadata->>'study_type' IS NOT NULL
                GROUP BY metadata->>'study_type'
                ORDER BY count DESC
            """
            study_types = await conn.fetch(study_types_sql)
            
            # Get trial statuses
            statuses_sql = """
                SELECT metadata->>'status' as status,
                       COUNT(*) as count
                FROM documents
                WHERE metadata->>'status' IS NOT NULL
                GROUP BY metadata->>'status'
                ORDER BY count DESC
            """
            statuses = await conn.fetch(statuses_sql)
            
            # Get publication types - Fixed query
            pub_types_sql = """
                WITH pub_type_data AS (
                    SELECT jsonb_array_elements_text(metadata->'article_types') as pub_type
                    FROM documents
                    WHERE metadata->'article_types' IS NOT NULL
                    AND jsonb_typeof(metadata->'article_types') = 'array'
                )
                SELECT pub_type, COUNT(*) as count
                FROM pub_type_data
                WHERE pub_type IS NOT NULL
                GROUP BY pub_type
                ORDER BY count DESC
                LIMIT 20
            """
            pub_types = await conn.fetch(pub_types_sql)
            
            # Get journals
            journals_sql = """
                SELECT metadata->>'journal' as journal,
                       COUNT(*) as count
                FROM documents
                WHERE metadata->>'journal' IS NOT NULL
                GROUP BY metadata->>'journal'
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
                        AND metadata->>'start_date' ~ '^\d{4}-\d{2}-\d{2}'
                        THEN (metadata->>'start_date')::date 
                        ELSE NULL 
                    END) as min_publication_date,
                    MAX(CASE 
                        WHEN metadata->>'start_date' IS NOT NULL 
                        AND metadata->>'start_date' ~ '^\d{4}-\d{2}-\d{2}'
                        THEN (metadata->>'start_date')::date 
                        ELSE NULL 
                    END) as max_publication_date
                FROM documents
            """
            date_ranges = await conn.fetchrow(date_ranges_sql)
        
        return {
            "sources": [{"name": r['name'], "type": r['type'], "count": r['document_count']} for r in sources],
            "sourceTypes": [{"type": r['type'], "count": r['document_count']} for r in source_types],
            "diseases": [{"name": r['name'], "count": r['document_count']} for r in diseases],
            "studyPhases": [{"value": r['phase'], "count": r['count']} for r in phases if r['phase']],
            "studyTypes": [{"value": r['study_type'], "count": r['count']} for r in study_types if r['study_type']],
            "trialStatuses": [{"value": r['status'], "count": r['count']} for r in statuses if r['status']],
            "publicationTypes": [{"value": r['pub_type'], "count": r['count']} for r in pub_types if r['pub_type']],
            "journals": [{"value": r['journal'], "count": r['count']} for r in journals if r['journal']],
            "dateRanges": {
                "min_created_date": date_ranges['min_created_date'].isoformat() if date_ranges['min_created_date'] else None,
                "max_created_date": date_ranges['max_created_date'].isoformat() if date_ranges['max_created_date'] else None,
                "min_publication_date": date_ranges['min_publication_date'].isoformat() if date_ranges['min_publication_date'] else None,
                "max_publication_date": date_ranges['max_publication_date'].isoformat() if date_ranges['max_publication_date'] else None,
            }
        }
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))