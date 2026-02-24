from fastapi import APIRouter, Depends
from typing import Dict, Any
from datetime import datetime
from core.auth import get_current_admin
from core.database import get_pg_connection
from loguru import logger

router = APIRouter(prefix="/api/admin", tags=["admin-base"])

@router.get("/dashboard/stats", dependencies=[Depends(get_current_admin)])
async def get_dashboard_stats() -> Dict[str, Any]:
    """Get dashboard statistics"""
    async with get_pg_connection() as conn:
        # Get counts
        sources_count = await conn.fetchval("SELECT COUNT(*) FROM sources WHERE is_active = true")
        diseases_count = await conn.fetchval("SELECT COUNT(*) FROM diseases")
        documents_count = await conn.fetchval("SELECT COUNT(*) FROM documents")
        jobs_count = await conn.fetchval("SELECT COUNT(*) FROM crawl_jobs WHERE created_at > NOW() - INTERVAL '24 hours'")
        
        # Get recent job stats
        recent_jobs = await conn.fetch("""
            SELECT 
                status,
                COUNT(*) as count,
                SUM(documents_found) as total_found,
                SUM(documents_processed) as total_processed,
                SUM(errors) as total_errors
            FROM crawl_jobs
            WHERE created_at > NOW() - INTERVAL '7 days'
            GROUP BY status
        """)
        
        # Get top diseases by document count
        top_diseases = await conn.fetch("""
            SELECT 
                dc.name,
                COUNT(DISTINCT dd.document_id) as document_count
            FROM diseases dc
            JOIN document_diseases dd ON dc.id = dd.disease_id
            GROUP BY dc.id, dc.name
            ORDER BY document_count DESC
            LIMIT 10
        """)
        
        # Get source activity
        source_activity = await conn.fetch("""
            SELECT 
                s.name,
                s.last_crawled,
                COUNT(DISTINCT d.id) as document_count,
                COUNT(DISTINCT cj.id) as job_count
            FROM sources s
            LEFT JOIN documents d ON s.id = d.source_id
            LEFT JOIN crawl_jobs cj ON s.id = cj.source_id AND cj.created_at > NOW() - INTERVAL '7 days'
            WHERE s.is_active = true
            GROUP BY s.id, s.name, s.last_crawled
            ORDER BY s.name
        """)
        
        return {
            "overview": {
                "sources": sources_count,
                "diseases": diseases_count,
                "documents": documents_count,
                "recent_jobs": jobs_count
            },
            "job_stats": [dict(job) for job in recent_jobs],
            "top_diseases": [dict(disease) for disease in top_diseases],
            "source_activity": [dict(source) for source in source_activity],
            "last_updated": datetime.now().isoformat()
        }

@router.get("/health", dependencies=[Depends(get_current_admin)])
async def health_check() -> Dict[str, Any]:
    """Check system health"""
    health_status = {
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "checks": {}
    }
    
    # Check database
    try:
        async with get_pg_connection() as conn:
            await conn.fetchval("SELECT 1")
            health_status["checks"]["database"] = "ok"
    except Exception as e:
        health_status["checks"]["database"] = f"error: {str(e)}"
        health_status["status"] = "unhealthy"
    
    # Redis removed in cleanup
    
    return health_status