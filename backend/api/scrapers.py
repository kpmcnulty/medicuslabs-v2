from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, text
from typing import List, Dict, Any
from loguru import logger

from core.database import get_db
from models.database import Source, CrawlJob, Document
from models.schemas import (
    ScrapeRequest, ScrapeResponse, CrawlJobResponse,
    DocumentResponse, SourceResponse
)
from tasks.scrapers import scrape_clinicaltrials, scrape_pubmed, scrape_all_sources
from tasks.scheduled import (
    daily_incremental_update, 
    weekly_full_check,
    scrape_specific_disease
)

router = APIRouter(prefix="/api/scrapers", tags=["scrapers"])

@router.post("/trigger", response_model=ScrapeResponse)
async def trigger_scrape(request: ScrapeRequest, db: AsyncSession = Depends(get_db)):
    """Trigger a scraping job for specified disease terms"""
    
    # Validate source
    source_name_lower = request.source_name.lower()
    
    # Map source names to Celery tasks
    task_map = {
        "clinicaltrials": scrape_clinicaltrials,
        "clinicaltrials.gov": scrape_clinicaltrials,
        "pubmed": scrape_pubmed,
        "all": scrape_all_sources
    }
    
    if source_name_lower not in task_map:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid source: {request.source_name}. Valid sources: {list(task_map.keys())}"
        )
    
    # Launch Celery task
    task = task_map[source_name_lower]
    result = task.delay(request.disease_terms, **request.options)
    
    return ScrapeResponse(
        job_id=0,  # We'll improve this to track actual job IDs
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

@router.post("/incremental", response_model=ScrapeResponse)
async def trigger_incremental_update():
    """Manually trigger an incremental update for all sources"""
    
    # Launch the daily incremental update task
    result = daily_incremental_update.delay()
    
    return ScrapeResponse(
        job_id=0,  # Task ID tracking to be implemented
        message="Incremental update started for all sources",
        status="started"
    )

@router.post("/incremental/{disease_term}", response_model=ScrapeResponse)
async def trigger_disease_update(disease_term: str, sources: List[str] = None):
    """Trigger incremental update for a specific disease"""
    
    # Launch the specific disease scrape task
    result = scrape_specific_disease.delay(disease_term, sources)
    
    return ScrapeResponse(
        job_id=0,
        message=f"Incremental update started for disease: {disease_term}",
        status="started"
    )

@router.post("/full-check", response_model=ScrapeResponse)
async def trigger_full_check():
    """Manually trigger a full check of stale documents"""
    
    # Launch the weekly full check task
    result = weekly_full_check.delay()
    
    return ScrapeResponse(
        job_id=0,
        message="Full document check started",
        status="started"
    )

@router.get("/sources", response_model=List[Dict[str, Any]])
async def list_sources(db: AsyncSession = Depends(get_db)):
    """List all available sources with document counts"""
    
    # Query to get sources with document counts
    query = text("""
        SELECT 
            s.id,
            s.name,
            s.type,
            s.base_url,
            s.config,
            s.is_active,
            s.last_crawled,
            s.category,
            s.rate_limit,
            s.requires_auth,
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
            "type": row.type,
            "base_url": row.base_url,
            "config": row.config,
            "is_active": row.is_active,
            "last_crawled": row.last_crawled,
            "category": row.category,
            "rate_limit": row.rate_limit,
            "requires_auth": row.requires_auth,
            "scraper_type": row.scraper_type,
            "created_at": row.created_at,
            "updated_at": row.updated_at,
            "document_count": row.document_count
        }
        sources.append(source_dict)
    
    return sources

@router.get("/sources/by-category", response_model=Dict[str, List[Dict[str, Any]]])
async def list_sources_by_category(db: AsyncSession = Depends(get_db)):
    """List all available sources grouped by category"""
    
    # Get all sources
    sources = await list_sources(db)
    
    # Group by category
    grouped = {}
    for source in sources:
        category = source.get('category', 'uncategorized')
        if category not in grouped:
            grouped[category] = []
        grouped[category].append(source)
    
    return grouped

@router.get("/sources/{source_id}/documents", response_model=List[DocumentResponse])
async def get_source_documents(
    source_id: int,
    limit: int = 50,
    offset: int = 0,
    db: AsyncSession = Depends(get_db)
):
    """Get documents from a specific source"""
    
    # Verify source exists
    source_result = await db.execute(
        select(Source).where(Source.id == source_id)
    )
    source = source_result.scalar_one_or_none()
    
    if not source:
        raise HTTPException(status_code=404, detail="Source not found")
    
    # Get documents
    result = await db.execute(
        select(Document)
        .where(Document.source_id == source_id)
        .order_by(Document.created_at.desc())
        .limit(limit)
        .offset(offset)
    )
    documents = result.scalars().all()
    
    # Convert to response format with metadata mapping
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
    
    # Convert to response format with metadata mapping
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