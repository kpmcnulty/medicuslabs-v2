from celery import shared_task
from celery.schedules import crontab
from loguru import logger
from datetime import datetime, timedelta
from typing import Dict, Any, List
import asyncio

from tasks import celery_app
from scrapers.clinicaltrials import ClinicalTrialsScraper
from scrapers.pubmed import PubMedScraper
from core.config import settings
from core.database import get_pg_connection

# Configure periodic tasks
celery_app.conf.beat_schedule = {
    'daily-incremental-update': {
        'task': 'tasks.scheduled.daily_incremental_update',
        'schedule': crontab(hour=2, minute=0),  # Run at 2 AM UTC daily
    },
    'weekly-full-check': {
        'task': 'tasks.scheduled.weekly_full_check',
        'schedule': crontab(day_of_week=0, hour=3, minute=0),  # Run at 3 AM UTC on Sundays
    },
    'hourly-status-check': {
        'task': 'tasks.scheduled.check_running_jobs',
        'schedule': crontab(minute=0),  # Run every hour
    },
}

@shared_task
def daily_incremental_update() -> Dict[str, Any]:
    """Run daily incremental updates for all active sources"""
    logger.info("Starting daily incremental update")
    
    results = {
        "started_at": datetime.now().isoformat(),
        "sources": {}
    }
    
    # Get disease terms from settings or database
    disease_terms = asyncio.run(get_active_disease_terms())
    
    # Run ClinicalTrials.gov incremental update
    try:
        ct_results = asyncio.run(run_ct_incremental(disease_terms, 500))
        results["sources"]["clinicaltrials"] = ct_results
    except Exception as e:
        logger.error(f"Error in ClinicalTrials incremental update: {e}")
        results["sources"]["clinicaltrials"] = {"error": str(e)}
    
    # Run PubMed incremental update
    try:
        pm_results = asyncio.run(run_pm_incremental(disease_terms, 200))
        results["sources"]["pubmed"] = pm_results
    except Exception as e:
        logger.error(f"Error in PubMed incremental update: {e}")
        results["sources"]["pubmed"] = {"error": str(e)}
    
    results["completed_at"] = datetime.now().isoformat()
    logger.info(f"Daily incremental update completed: {results}")
    
    return results

@shared_task
def weekly_full_check() -> Dict[str, Any]:
    """
    Weekly check for documents that haven't been updated in a while.
    This catches any documents that might have been missed.
    """
    logger.info("Starting weekly full check")
    
    results = {
        "started_at": datetime.now().isoformat(),
        "documents_checked": 0,
        "documents_updated": 0
    }
    
    # Run the async helper function
    stale_results = asyncio.run(get_stale_documents())
    results.update(stale_results)
    
    results["completed_at"] = datetime.now().isoformat()
    logger.info(f"Weekly full check completed: {results}")
    
    return results

@shared_task
def check_running_jobs() -> Dict[str, Any]:
    """Check for stuck jobs and mark them as failed if needed"""
    logger.info("Checking for stuck crawl jobs")
    
    results = {
        "checked_at": datetime.now().isoformat(),
        "stuck_jobs": []
    }
    
    stuck_jobs = asyncio.run(check_stuck_jobs())
    results["stuck_jobs"] = stuck_jobs
    
    return results

@shared_task
def scrape_specific_disease(disease_term: str, sources: List[str] = None) -> Dict[str, Any]:
    """
    On-demand scraping for a specific disease term.
    Can be triggered manually or via API.
    """
    logger.info(f"Starting specific scrape for disease: {disease_term}")
    
    if sources is None:
        sources = ["clinicaltrials", "pubmed"]
    
    results = {
        "disease_term": disease_term,
        "started_at": datetime.now().isoformat(),
        "sources": {}
    }
    
    if "clinicaltrials" in sources:
        try:
            ct_results = asyncio.run(run_ct_incremental([disease_term], 100))
            results["sources"]["clinicaltrials"] = ct_results
        except Exception as e:
            logger.error(f"Error scraping ClinicalTrials for {disease_term}: {e}")
            results["sources"]["clinicaltrials"] = {"error": str(e)}
    
    if "pubmed" in sources:
        try:
            pm_results = asyncio.run(run_pm_incremental([disease_term], 50))
            results["sources"]["pubmed"] = pm_results
        except Exception as e:
            logger.error(f"Error scraping PubMed for {disease_term}: {e}")
            results["sources"]["pubmed"] = {"error": str(e)}
    
    results["completed_at"] = datetime.now().isoformat()
    return results

async def get_active_disease_terms() -> List[str]:
    """Get list of active disease terms to monitor"""
    async with get_pg_connection() as conn:
        # Check if we have diseases in the database
        diseases = await conn.fetch("""
            SELECT name FROM diseases WHERE id IN (
                SELECT DISTINCT disease_id FROM document_diseases
            )
            LIMIT 20
        """)
        
        if diseases:
            return [d['name'] for d in diseases]
        
        # Fallback to default terms
        return settings.default_disease_terms or [
            "diabetes",
            "COVID-19",
            "cancer",
            "hypertension",
            "heart disease"
        ]

# Helper async functions for running in sync context
async def run_ct_incremental(disease_terms: List[str], max_results: int) -> Dict[str, Any]:
    """Run ClinicalTrials incremental update"""
    async with ClinicalTrialsScraper() as scraper:
        return await scraper.scrape_incremental(
            disease_terms=disease_terms,
            max_results=max_results
        )

async def run_pm_incremental(disease_terms: List[str], max_results: int) -> Dict[str, Any]:
    """Run PubMed incremental update"""
    async with PubMedScraper() as scraper:
        return await scraper.scrape_incremental(
            disease_terms=disease_terms,
            max_results=max_results
        )

async def get_stale_documents():
    """Get documents that haven't been checked in 7 days"""
    async with get_pg_connection() as conn:
        # Find documents not checked in over 7 days
        stale_docs = await conn.fetch("""
            SELECT DISTINCT external_id, source_id
            FROM documents
            WHERE last_checked_at < CURRENT_TIMESTAMP - INTERVAL '7 days'
               OR last_checked_at IS NULL
            ORDER BY last_checked_at ASC NULLS FIRST
            LIMIT 1000
        """)
        
        # Group by source
        by_source = {}
        for doc in stale_docs:
            source_id = doc['source_id']
            if source_id not in by_source:
                by_source[source_id] = []
            by_source[source_id].append(doc['external_id'])
        
        # Re-fetch each document
        results = {"documents_checked": 0, "documents_updated": 0}
        
        for source_id, external_ids in by_source.items():
            if source_id == 1:  # ClinicalTrials.gov
                async with ClinicalTrialsScraper() as scraper:
                    for ext_id in external_ids[:50]:  # Limit per run
                        try:
                            details = await scraper.fetch_details(ext_id)
                            document, source_updated_at = scraper.extract_document_data(details)
                            await scraper.save_document(document, source_updated_at)
                            results["documents_checked"] += 1
                            results["documents_updated"] += 1
                        except Exception as e:
                            logger.error(f"Error checking CT {ext_id}: {e}")
                            
            elif source_id == 2:  # PubMed
                async with PubMedScraper() as scraper:
                    for ext_id in external_ids[:50]:
                        try:
                            details = await scraper.fetch_details(ext_id)
                            document, source_updated_at = scraper.extract_document_data(details)
                            await scraper.save_document(document, source_updated_at)
                            results["documents_checked"] += 1
                            results["documents_updated"] += 1
                        except Exception as e:
                            logger.error(f"Error checking PMID {ext_id}: {e}")
        
        return results

async def check_stuck_jobs():
    """Check for stuck jobs and mark them as failed"""
    async with get_pg_connection() as conn:
        # Find jobs running for more than 6 hours
        stuck_jobs = await conn.fetch("""
            UPDATE crawl_jobs
            SET status = 'failed',
                completed_at = CURRENT_TIMESTAMP,
                error_details = error_details || jsonb_build_array(
                    jsonb_build_object(
                        'error', 'Job timed out after 6 hours',
                        'timestamp', CURRENT_TIMESTAMP
                    )
                )
            WHERE status = 'running'
              AND started_at < CURRENT_TIMESTAMP - INTERVAL '6 hours'
            RETURNING id, source_id, started_at
        """)
        
        results = []
        for job in stuck_jobs:
            logger.warning(f"Marked job {job['id']} as failed due to timeout")
            results.append({
                "job_id": job['id'],
                "source_id": job['source_id'],
                "started_at": job['started_at'].isoformat()
            })
        
        return results