from typing import List, Dict, Any
import asyncio
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
    """Scrape all primary sources for the given diseases"""
    disease_ids = kwargs.get('disease_ids', [])
    disease_names = kwargs.get('disease_names', [])
    
    logger.info(f"Starting scrape of all sources for diseases: {disease_names} (IDs: {disease_ids})")
    
    # Launch tasks in parallel
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
            "total_errors": total_errors
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