from typing import List, Dict, Any
import asyncio
from loguru import logger

from . import celery_app
from scrapers.clinicaltrials import ClinicalTrialsScraper
from scrapers.pubmed import PubMedScraper

@celery_app.task(name="scrape_clinicaltrials")
def scrape_clinicaltrials(disease_terms: List[str], **kwargs) -> Dict[str, Any]:
    """Celery task to scrape ClinicalTrials.gov"""
    logger.info(f"Starting ClinicalTrials.gov scrape for terms: {disease_terms}")
    
    async def run_scraper():
        async with ClinicalTrialsScraper() as scraper:
            return await scraper.scrape(disease_terms, **kwargs)
    
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
def scrape_pubmed(disease_terms: List[str], **kwargs) -> Dict[str, Any]:
    """Celery task to scrape PubMed"""
    logger.info(f"Starting PubMed scrape for terms: {disease_terms}")
    
    async def run_scraper():
        async with PubMedScraper() as scraper:
            return await scraper.scrape(disease_terms, **kwargs)
    
    # Run async scraper in sync context
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        result = loop.run_until_complete(run_scraper())
        logger.info(f"PubMed scrape completed: {result}")
        return result
    finally:
        loop.close()

@celery_app.task(name="scrape_all_sources")
def scrape_all_sources(disease_terms: List[str], **kwargs) -> Dict[str, Any]:
    """Scrape all primary sources for the given disease terms"""
    logger.info(f"Starting scrape of all sources for terms: {disease_terms}")
    
    # Launch tasks in parallel
    group_result = celery_app.group([
        scrape_clinicaltrials.s(disease_terms, **kwargs),
        scrape_pubmed.s(disease_terms, **kwargs)
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