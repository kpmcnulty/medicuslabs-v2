from celery import shared_task
from celery.schedules import crontab
from loguru import logger
from datetime import datetime
from typing import Dict, Any

from tasks import celery_app

# Simple schedule - just run everything daily
celery_app.conf.beat_schedule = {
    'daily-update-all': {
        'task': 'tasks.scheduled.update_all_sources',
        'schedule': crontab(hour=2, minute=0),  # 2 AM UTC daily
    },
    'hourly-cleanup': {
        'task': 'tasks.scheduled.cleanup_stuck_jobs',
        'schedule': crontab(minute=0),  # Every hour
    },
}

@shared_task
def update_all_sources() -> Dict[str, Any]:
    """
    Daily task that updates ALL active sources.
    Gets ALL available data - no artificial limits.
    """
    logger.info("Starting daily update for all active sources")
    
    # Import here to avoid circular imports
    from tasks.scrapers import scrape_all_sources
    
    # Call the function directly (not as a subtask) since we're already in a task
    result = scrape_all_sources(
        disease_ids=[],  # Empty = use all configured diseases
        disease_names=[],
        options={
            'limit': None,  # No limit - get everything
            'incremental': True  # Only get new/updated since last run
        }
    )
    
    return {
        "started_at": datetime.now().isoformat(),
        "message": "Update all sources task triggered - fetching new/updated data since last run",
        **result  # Include task_ids and other info
    }

@shared_task  
def cleanup_stuck_jobs() -> Dict[str, Any]:
    """
    Hourly cleanup of stuck jobs.
    Simple health check to keep system running smoothly.
    """
    logger.info("Running cleanup check")
    
    import asyncio
    from core.database import get_pg_connection
    
    async def do_cleanup():
        async with get_pg_connection() as conn:
            # Mark jobs stuck >6 hours as failed
            result = await conn.execute("""
                UPDATE crawl_jobs
                SET status = 'failed',
                    completed_at = CURRENT_TIMESTAMP,
                    error_details = COALESCE(error_details, '[]'::jsonb) || 
                        jsonb_build_array(jsonb_build_object(
                            'error', 'Job timed out after 6 hours',
                            'timestamp', CURRENT_TIMESTAMP
                        ))
                WHERE status = 'running'
                AND started_at < CURRENT_TIMESTAMP - INTERVAL '6 hours'
            """)
            return int(result.split()[-1]) if result else 0
    
    stuck_count = asyncio.run(do_cleanup())
    
    return {
        "checked_at": datetime.now().isoformat(),
        "stuck_jobs_cleaned": stuck_count
    }