from celery import shared_task
from celery.result import AsyncResult
from typing import List, Dict, Any
from loguru import logger
import asyncio
from core.database import get_pg_connection

@shared_task
def aggregate_scraper_results(task_ids: List[str]) -> Dict[str, Any]:
    """
    Aggregate results from multiple scraper tasks.
    This runs as a separate task after scrapers are queued.
    """
    logger.info(f"Aggregating results from {len(task_ids)} tasks")
    
    results = []
    completed = 0
    failed = 0
    
    # Check each task result
    for task_id in task_ids:
        result = AsyncResult(task_id)
        
        if result.ready():
            if result.successful():
                results.append(result.result)
                completed += 1
            else:
                failed += 1
                logger.error(f"Task {task_id} failed: {result.info}")
        else:
            logger.info(f"Task {task_id} still pending")
    
    # Aggregate metrics
    total_found = sum(
        r.get("documents_found", r.get("total_found", 0)) 
        if isinstance(r, dict) else 0 
        for r in results
    )
    total_processed = sum(
        r.get("documents_processed", r.get("total_processed", 0)) 
        if isinstance(r, dict) else 0 
        for r in results
    )
    
    return {
        "task_ids": task_ids,
        "completed": completed,
        "failed": failed,
        "pending": len(task_ids) - completed - failed,
        "total_documents_found": total_found,
        "total_documents_processed": total_processed,
        "results": results
    }

@shared_task
def monitor_scraper_group(task_ids: List[str], check_interval: int = 30) -> Dict[str, Any]:
    """
    Monitor a group of scraper tasks and update aggregate status.
    Runs periodically until all tasks complete.
    """
    logger.info(f"Starting monitor for {len(task_ids)} tasks")
    
    # Store group status in database
    async def update_group_status():
        async with get_pg_connection() as conn:
            # Create a group tracking record
            group_id = await conn.fetchval("""
                INSERT INTO scraper_groups (task_ids, status, created_at)
                VALUES ($1, 'running', CURRENT_TIMESTAMP)
                RETURNING id
            """, task_ids)
            
            while True:
                # Check task statuses
                all_complete = True
                statuses = []
                
                for task_id in task_ids:
                    result = AsyncResult(task_id)
                    statuses.append({
                        "task_id": task_id,
                        "ready": result.ready(),
                        "successful": result.successful() if result.ready() else None
                    })
                    
                    if not result.ready():
                        all_complete = False
                
                # Update group status
                await conn.execute("""
                    UPDATE scraper_groups 
                    SET 
                        task_statuses = $1,
                        updated_at = CURRENT_TIMESTAMP
                    WHERE id = $2
                """, statuses, group_id)
                
                if all_complete:
                    # Final aggregation
                    result = aggregate_scraper_results(task_ids)
                    
                    await conn.execute("""
                        UPDATE scraper_groups 
                        SET 
                            status = 'completed',
                            result = $1,
                            completed_at = CURRENT_TIMESTAMP
                        WHERE id = $2
                    """, result, group_id)
                    
                    return result
                
                # Wait before next check
                await asyncio.sleep(check_interval)
    
    # Run async monitor
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        return loop.run_until_complete(update_group_status())
    finally:
        loop.close()