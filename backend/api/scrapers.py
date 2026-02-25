from fastapi import APIRouter, HTTPException, Depends, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, text
from typing import List, Dict, Any
from datetime import datetime
import json
import asyncio
from loguru import logger

from core.database import get_db
from models.database import Source, CrawlJob, Document, Disease
from models.schemas import (
    ScrapeRequest, ScrapeResponse, CrawlJobResponse,
    DocumentResponse, SourceResponse
)

# Import scraper classes directly
from scrapers.clinicaltrials import ClinicalTrialsScraper
from scrapers.pubmed import PubMedScraper
from scrapers.reddit import RedditScraper
from scrapers.faers import FAERSScraper
from scrapers.google_news import GoogleNewsScraper
from scrapers.healthunlocked import HealthUnlockedScraper
from scrapers.medical_news_today import MedicalNewsTodayScraper
from scrapers.stackexchange_health import StackExchangeHealthScraper
from scrapers.biorxiv import BioRxivScraper
from scrapers.openfda import OpenFDAScraper
from scrapers.who_don import WHODiseaseOutbreakNewsScraper
from scrapers.semantic_scholar import SemanticScholarScraper
from scrapers.drugscom import DrugsComScraper
from scrapers.reddit_search import RedditSearchScraper
from scrapers.bensfriends import BensFriendsScraper
from scrapers.myhealthteam import MyHealthTeamScraper
from scrapers.inspire import InspireScraper
from scrapers.pullpush import PullpushScraper
from scrapers.patientinfo import PatientInfoScraper
from scrapers.healingwell import HealingWellScraper

router = APIRouter(prefix="/api/scrapers", tags=["scrapers"])


async def run_scraper_task(
    scraper_class,
    disease_names: List[str],
    job_id: int,
    source_id: int,
    source_name: str,
    options: Dict[str, Any]
):
    """Background task to run a scraper"""
    try:
        logger.info(f"Starting scraper task for {source_name}, job {job_id}")

        # Initialize scraper with source_id
        scraper = scraper_class(source_id=source_id)

        # Get disease IDs from names
        from core.database import get_pg_connection
        async with get_pg_connection() as conn:
            disease_rows = await conn.fetch(
                "SELECT id, name FROM diseases WHERE name = ANY($1)", disease_names
            )
            disease_ids = [r['id'] for r in disease_rows]
            disease_name_list = [r['name'] for r in disease_rows]

        logger.info(f"Scraping {source_name} for diseases: {disease_name_list}")
        await scraper.scrape(disease_ids=disease_ids, disease_names=disease_name_list, **options)

        # Update job status to completed
        from core.database import async_session_maker
        async with async_session_maker() as db:
            await db.execute(
                text("""
                    UPDATE crawl_jobs
                    SET status = 'completed', completed_at = :completed_at
                    WHERE id = :job_id
                """),
                {"job_id": job_id, "completed_at": datetime.now()}
            )
            await db.commit()

        logger.info(f"Scraper task completed for {source_name}, job {job_id}")
    except Exception as e:
        logger.error(f"Scraper task failed for {source_name}, job {job_id}: {str(e)}")

        # Update job status to failed
        from core.database import async_session_maker
        async with async_session_maker() as db:
            await db.execute(
                text("""
                    UPDATE crawl_jobs
                    SET status = 'failed', completed_at = :completed_at, error_details = :error
                    WHERE id = :job_id
                """),
                {"job_id": job_id, "completed_at": datetime.now(), "error": str(e)}
            )
            await db.commit()


@router.post("/trigger", response_model=ScrapeResponse)
async def trigger_scrape(
    request: ScrapeRequest,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db)
):
    """Trigger a scraping job for specified diseases"""

    # Validate source
    source_name_lower = request.source_name.lower()

    # Map source names to scraper classes
    scraper_map = {
        "clinicaltrials": ClinicalTrialsScraper,
        "clinicaltrials.gov": ClinicalTrialsScraper,
        "pubmed": PubMedScraper,
        "reddit": RedditScraper,
        "reddit medical": RedditScraper,
        "faers": FAERSScraper,
        "fda faers": FAERSScraper,
        "google news": GoogleNewsScraper,
        "googlenews": GoogleNewsScraper,
        "healthunlocked": HealthUnlockedScraper,
        "health unlocked": HealthUnlockedScraper,
        "medical news today": MedicalNewsTodayScraper,
        "medicalnewstoday": MedicalNewsTodayScraper,
        "stack exchange health": StackExchangeHealthScraper,
        "stackexchange": StackExchangeHealthScraper,
        "biorxiv": BioRxivScraper,
        "biorxiv/medrxiv": BioRxivScraper,
        "medrxiv": BioRxivScraper,
        "openfda": OpenFDAScraper,
        "openfda drug labels": OpenFDAScraper,
        "who disease outbreak news": WHODiseaseOutbreakNewsScraper,
        "who don": WHODiseaseOutbreakNewsScraper,
        "semantic scholar": SemanticScholarScraper,
        "semanticscholar": SemanticScholarScraper,
        "drugs.com": DrugsComScraper,
        "drugscom": DrugsComScraper,
        "reddit search": RedditSearchScraper,
        "redditsearch": RedditSearchScraper,
        "ben's friends": BensFriendsScraper,
        "bensfriends": BensFriendsScraper,
        "bens friends": BensFriendsScraper,
        "myhealthteam": MyHealthTeamScraper,
        "my health team": MyHealthTeamScraper,
        "inspire": InspireScraper,
        "inspire.com": InspireScraper,
        "pullpush": PullpushScraper,
        "pullpush reddit": PullpushScraper,
        "pullpush.io": PullpushScraper,
        "patient.info": PatientInfoScraper,
        "patientinfo": PatientInfoScraper,
        "patient.info forums": PatientInfoScraper,
        "healingwell": HealingWellScraper,
        "healing well": HealingWellScraper,
    }

    if source_name_lower not in scraper_map:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid source: {request.source_name}. Valid sources: {list(scraper_map.keys())}"
        )

    # Get disease names for the provided IDs
    disease_query = await db.execute(
        select(Disease).where(Disease.id.in_(request.disease_ids))
    )
    diseases = disease_query.scalars().all()

    if len(diseases) != len(request.disease_ids):
        raise HTTPException(
            status_code=400,
            detail="One or more disease IDs not found"
        )

    # Get source ID
    source_result = await db.execute(
        select(Source).where(Source.name.ilike(f"%{request.source_name}%"))
    )
    source = source_result.scalar_one_or_none()

    if not source:
        raise HTTPException(status_code=400, detail=f"Source not found: {request.source_name}")

    # Create crawl job
    job_result = await db.execute(
        text("""
            INSERT INTO crawl_jobs (source_id, status, started_at, config)
            VALUES (:source_id, 'running', :started_at, :config)
            RETURNING id
        """),
        {
            "source_id": source.id,
            "started_at": datetime.now(),
            "config": json.dumps({
                "disease_ids": request.disease_ids,
                "disease_names": [d.name for d in diseases],
                **request.options
            })
        }
    )
    job_id = job_result.scalar_one()
    await db.commit()

    # Launch background task
    scraper_class = scraper_map[source_name_lower]
    background_tasks.add_task(
        run_scraper_task,
        scraper_class=scraper_class,
        disease_names=[d.name for d in diseases],
        job_id=job_id,
        source_id=source.id,
        source_name=source.name,
        options=request.options
    )

    return ScrapeResponse(
        job_id=job_id,
        message=f"Scraping job started for {request.source_name}",
        status="started"
    )


@router.get("/jobs/{job_id}", response_model=CrawlJobResponse)
async def get_job_status(job_id: int, db: AsyncSession = Depends(get_db)):
    """Get status of a specific crawl job"""

    result = await db.execute(
        select(CrawlJob).where(CrawlJob.id == job_id)
    )
    job = result.scalar_one_or_none()

    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    return CrawlJobResponse.model_validate(job)


@router.get("/jobs", response_model=List[CrawlJobResponse])
async def list_jobs(
    source_id: int = None,
    status: str = None,
    limit: int = 10,
    offset: int = 0,
    db: AsyncSession = Depends(get_db)
):
    """List crawl jobs with optional filters"""

    query = select(CrawlJob).order_by(CrawlJob.created_at.desc())

    if source_id:
        query = query.where(CrawlJob.source_id == source_id)
    if status:
        query = query.where(CrawlJob.status == status)

    query = query.limit(limit).offset(offset)

    result = await db.execute(query)
    jobs = result.scalars().all()

    return [CrawlJobResponse.model_validate(job) for job in jobs]


@router.get("/sources", response_model=List[Dict[str, Any]])
async def list_sources(db: AsyncSession = Depends(get_db)):
    """List all available sources with document counts"""

    query = text("""
        SELECT
            s.id,
            s.name,
            
            s.base_url,
            s.config,
            s.is_active,
            s.last_crawled,
            s.category,
            s.rate_limit,
            
            s.scraper_type,
            s.created_at,
            s.updated_at,
            COUNT(d.id) as document_count
        FROM sources s
        LEFT JOIN documents d ON s.id = d.source_id
        WHERE s.is_active = true
        GROUP BY s.id
        ORDER BY s.category, s.name
    """)

    result = await db.execute(query)
    sources = []

    for row in result:
        source_dict = {
            "id": row.id,
            "name": row.name,
            
            "base_url": row.base_url,
            "config": row.config,
            "is_active": row.is_active,
            "last_crawled": row.last_crawled,
            "category": row.category,
            "rate_limit": row.rate_limit,
            
            "scraper_type": row.scraper_type,
            "created_at": row.created_at,
            "updated_at": row.updated_at,
            "document_count": row.document_count
        }
        sources.append(source_dict)

    return sources


@router.get("/sources/{source_id}/documents", response_model=List[DocumentResponse])
async def get_source_documents(
    source_id: int,
    limit: int = 50,
    offset: int = 0,
    db: AsyncSession = Depends(get_db)
):
    """Get documents from a specific source"""

    source_result = await db.execute(
        select(Source).where(Source.id == source_id)
    )
    source = source_result.scalar_one_or_none()

    if not source:
        raise HTTPException(status_code=404, detail="Source not found")

    result = await db.execute(
        select(Document)
        .where(Document.source_id == source_id)
        .order_by(Document.created_at.desc())
        .limit(limit)
        .offset(offset)
    )
    documents = result.scalars().all()

    responses = []
    for doc in documents:
        doc_dict = {
            "id": doc.id,
            "source_id": doc.source_id,
            "external_id": doc.external_id,
            "url": doc.url,
            "title": doc.title,
            "content": doc.content,
            "summary": doc.summary,
            "metadata": doc.doc_metadata,
            "status": doc.status,
            "language": doc.language,
            "relevance_score": doc.relevance_score,
            "created_at": doc.created_at,
            "updated_at": doc.updated_at,
            "scraped_at": doc.scraped_at
        }
        responses.append(DocumentResponse(**doc_dict))

    return responses


@router.get("/documents/recent", response_model=List[DocumentResponse])
async def get_recent_documents(
    limit: int = 20,
    db: AsyncSession = Depends(get_db)
):
    """Get recently scraped documents"""

    result = await db.execute(
        select(Document)
        .order_by(Document.scraped_at.desc())
        .limit(limit)
    )
    documents = result.scalars().all()

    responses = []
    for doc in documents:
        doc_dict = {
            "id": doc.id,
            "source_id": doc.source_id,
            "external_id": doc.external_id,
            "url": doc.url,
            "title": doc.title,
            "content": doc.content,
            "summary": doc.summary,
            "metadata": doc.doc_metadata,
            "status": doc.status,
            "language": doc.language,
            "relevance_score": doc.relevance_score,
            "created_at": doc.created_at,
            "updated_at": doc.updated_at,
            "scraped_at": doc.scraped_at
        }
        responses.append(DocumentResponse(**doc_dict))

    return responses
