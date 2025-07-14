from typing import List, Dict, Any
import asyncio
import json
from loguru import logger

from . import celery_app
from scrapers.clinicaltrials import ClinicalTrialsScraper
from scrapers.pubmed import PubMedScraper
from scrapers.reddit import RedditScraper

@celery_app.task(name="scrape_clinicaltrials")
def scrape_clinicaltrials(**kwargs) -> Dict[str, Any]:
    """Celery task to scrape ClinicalTrials.gov"""
    disease_ids = kwargs.pop('disease_ids', [])
    disease_names = kwargs.pop('disease_names', [])
    job_id = kwargs.pop('job_id', None)
    
    logger.info(f"Starting ClinicalTrials.gov scrape for diseases: {disease_names} (IDs: {disease_ids})")
    
    async def run_scraper():
        async with ClinicalTrialsScraper() as scraper:
            # Set the job_id if provided
            if job_id:
                scraper.job_id = job_id
            return await scraper.scrape(disease_ids, disease_names, **kwargs)
    
    # Run async scraper in sync context
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        result = loop.run_until_complete(run_scraper())
        logger.info(f"ClinicalTrials.gov scrape completed: {result}")
        return result
    finally:
        loop.close()

@celery_app.task(name="scrape_pubmed")
def scrape_pubmed(**kwargs) -> Dict[str, Any]:
    """Celery task to scrape PubMed"""
    disease_ids = kwargs.pop('disease_ids', [])
    disease_names = kwargs.pop('disease_names', [])
    job_id = kwargs.pop('job_id', None)
    
    logger.info(f"Starting PubMed scrape for diseases: {disease_names} (IDs: {disease_ids})")
    
    async def run_scraper():
        async with PubMedScraper() as scraper:
            # Set the job_id if provided
            if job_id:
                scraper.job_id = job_id
            return await scraper.scrape(disease_ids, disease_names, **kwargs)
    
    # Run async scraper in sync context
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        result = loop.run_until_complete(run_scraper())
        logger.info(f"PubMed scrape completed: {result}")
        return result
    finally:
        loop.close()

@celery_app.task(name="scrape_reddit")
def scrape_reddit(**kwargs) -> Dict[str, Any]:
    """Celery task to scrape Reddit"""
    disease_ids = kwargs.pop('disease_ids', [])
    disease_names = kwargs.pop('disease_names', [])
    job_id = kwargs.pop('job_id', None)
    source_id = kwargs.pop('source_id', None)
    source_name = kwargs.pop('source_name', 'Reddit')
    
    logger.info(f"Starting Reddit scrape for source {source_name} (ID: {source_id}) - diseases: {disease_names} (IDs: {disease_ids})")
    
    async def run_scraper():
        # For Reddit, we need to get the source_id from the database if not provided
        if not source_id:
            from core.database import get_pg_connection
            async with get_pg_connection() as conn:
                result = await conn.fetchrow(
                    "SELECT id FROM sources WHERE scraper_type = 'reddit_scraper' LIMIT 1"
                )
                if result:
                    actual_source_id = result['id']
                else:
                    raise ValueError("No Reddit source found in database")
        else:
            actual_source_id = source_id
            
        async with RedditScraper(source_id=actual_source_id, source_name=source_name) as scraper:
            # Set the job_id if provided
            if job_id:
                scraper.job_id = job_id
            return await scraper.scrape(disease_ids, disease_names, **kwargs)
    
    # Run async scraper in sync context
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        result = loop.run_until_complete(run_scraper())
        logger.info(f"Reddit scrape completed: {result}")
        return result
    finally:
        loop.close()

@celery_app.task(name="scrape_all_sources")
def scrape_all_sources(**kwargs) -> Dict[str, Any]:
    """Scrape ALL active sources from the database"""
    disease_ids = kwargs.get('disease_ids', [])
    disease_names = kwargs.get('disease_names', [])
    
    logger.info(f"Starting scrape of all active sources for diseases: {disease_names} (IDs: {disease_ids})")
    
    # Get all active sources from database
    async def get_active_sources():
        from core.database import get_pg_connection
        async with get_pg_connection() as conn:
            sources = await conn.fetch("""
                SELECT id, name, scraper_type, config 
                FROM sources 
                WHERE is_active = true
                ORDER BY id
            """)
            return sources
    
    # Run async function to get sources
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        sources = loop.run_until_complete(get_active_sources())
    finally:
        loop.close()
    
    if not sources:
        logger.warning("No active sources found")
        return {
            "results": [],
            "summary": {
                "total_documents_found": 0,
                "total_documents_processed": 0,
                "total_errors": 0,
                "message": "No active sources found"
            }
        }
    
    # Import web scraper task
    from tasks.web_scrapers import scrape_forum
    
    # Map scraper types to task functions
    task_map = {
        'clinicaltrials_api': scrape_clinicaltrials,
        'pubmed_api': scrape_pubmed,
        'reddit_scraper': scrape_reddit,
        'web_scraper': scrape_forum
    }
    
    # Build list of tasks to run
    tasks_to_run = []
    for source in sources:
        scraper_type = source['scraper_type']
        task_func = task_map.get(scraper_type)
        
        if not task_func:
            logger.warning(f"No task handler for source '{source['name']}' with scraper type: {scraper_type}")
            continue
            
        # Prepare kwargs for this source
        source_kwargs = kwargs.copy()
        source_kwargs['source_id'] = source['id']
        source_kwargs['source_name'] = source['name']
        
        # For web scrapers, pass config_name from source config
        if scraper_type == 'web_scraper' and source['config']:
            config_name = source['config'].get('config_name')
            if config_name:
                # Web scraper expects config_name as first arg
                tasks_to_run.append(
                    scrape_forum.s(config_name, disease_names or [], **source_kwargs)
                )
            else:
                logger.warning(f"Web scraper source '{source['name']}' missing config_name")
        else:
            # Regular scrapers
            tasks_to_run.append(task_func.s(**source_kwargs))
    
    if not tasks_to_run:
        logger.warning("No tasks to run")
        return {
            "results": [],
            "summary": {
                "total_documents_found": 0,
                "total_documents_processed": 0,
                "total_errors": 0,
                "message": "No valid scrapers found"
            }
        }
    
    # Launch all tasks in parallel
    logger.info(f"Running {len(tasks_to_run)} scraper tasks in parallel")
    group_result = celery_app.group(tasks_to_run).apply_async()
    
    # Wait for all tasks to complete
    results = group_result.get()
    
    # Aggregate results (handle both formats: documents_found/processed and total_found/processed)
    total_found = sum(
        r.get("documents_found", r.get("total_found", 0)) if isinstance(r, dict) else 0 
        for r in results
    )
    total_processed = sum(
        r.get("documents_processed", r.get("total_processed", 0)) if isinstance(r, dict) else 0 
        for r in results
    )
    total_errors = sum(
        len(r.get("errors", [])) if isinstance(r, dict) and isinstance(r.get("errors"), list) 
        else r.get("errors", 0) if isinstance(r, dict) else 0 
        for r in results
    )
    
    return {
        "results": results,
        "summary": {
            "total_documents_found": total_found,
            "total_documents_processed": total_processed,
            "total_errors": total_errors,
            "sources_processed": len(results)
        }
    }

@celery_app.task(name="scrape_incremental_all")
def scrape_incremental_all(**kwargs) -> Dict[str, Any]:
    """Run incremental scrape for all sources"""
    disease_ids = kwargs.get('disease_ids', [])
    disease_names = kwargs.get('disease_names', [])
    
    logger.info(f"Starting incremental scrape of all sources for diseases: {disease_names} (IDs: {disease_ids})")
    
    # Add incremental flag
    kwargs['is_incremental'] = True
    
    # Launch tasks in parallel with incremental flag
    group_result = celery_app.group([
        scrape_clinicaltrials.s(**kwargs),
        scrape_pubmed.s(**kwargs),
        scrape_reddit.s(**kwargs)
    ]).apply_async()
    
    # Wait for all tasks to complete
    results = group_result.get()
    
    # Aggregate results
    total_found = sum(r.get("documents_found", 0) for r in results)
    total_processed = sum(r.get("documents_processed", 0) for r in results)
    total_errors = sum(r.get("errors", 0) for r in results)
    
    return {
        "results": results,
        "summary": {
            "total_documents_found": total_found,
            "total_documents_processed": total_processed,
            "total_errors": total_errors,
            "type": "incremental"
        }
    }