from fastapi import APIRouter, HTTPException, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import List, Dict, Any, Optional
from loguru import logger

from core.database import get_db
from models.database import Source, SourceType
from models.schemas import ScrapeResponse
from tasks.web_scrapers import (
    scrape_forum, 
    scrape_all_forums,
    scrape_forum_incremental,
    test_forum_scraper
)

router = APIRouter(prefix="/api/scrapers/web", tags=["web-scrapers"])


@router.get("/sources")
async def list_web_sources(db: AsyncSession = Depends(get_db)) -> List[Dict[str, Any]]:
    """List all configured web scraping sources"""
    
    result = await db.execute(
        select(Source).where(
            Source.type == SourceType.secondary,
            Source.is_active == True
        )
    )
    sources = result.scalars().all()
    
    return [
        {
            "id": source.id,
            "name": source.name,
            "base_url": source.base_url,
            "config": source.config,
            "scraper_config": source.config.get("scraper_config") if source.config else None,
            "last_crawled": source.last_crawled
        }
        for source in sources
        if source.config and source.config.get("scraper_config")
    ]


@router.post("/trigger")
async def trigger_web_scrape(
    config_name: str,
    disease_terms: List[str] = Query(..., description="Disease terms to search"),
    max_pages: int = Query(5, ge=1, le=50, description="Max pages per term"),
    db: AsyncSession = Depends(get_db)
) -> ScrapeResponse:
    """Trigger web scraping for specific forum and disease terms"""
    
    # Validate config exists
    from sqlalchemy import text
    result = await db.execute(
        select(Source).where(
            text("config->>'scraper_config' = :config_name"),
            Source.is_active == True
        ).params(config_name=config_name)
    )
    source = result.scalar_one_or_none()
    
    if not source:
        raise HTTPException(
            status_code=404,
            detail=f"No active source found with config: {config_name}"
        )
    
    # Launch scraping task
    task = scrape_forum.delay(config_name, disease_terms, max_pages)
    
    return ScrapeResponse(
        job_id=0,  # TODO: Track actual Celery task ID
        message=f"Web scraping started for {source.name}",
        status="started",
        details={
            "source": source.name,
            "disease_terms": disease_terms,
            "max_pages": max_pages,
            "task_id": task.id
        }
    )


@router.post("/trigger-all")
async def trigger_all_forums(
    disease_terms: List[str] = Query(..., description="Disease terms to search"),
    max_pages: int = Query(3, ge=1, le=20, description="Max pages per term per forum")
) -> ScrapeResponse:
    """Trigger scraping for all configured forums"""
    
    # Launch task for all forums
    task = scrape_all_forums.delay(disease_terms, max_pages)
    
    return ScrapeResponse(
        job_id=0,
        message="Web scraping started for all forums",
        status="started",
        details={
            "disease_terms": disease_terms,
            "max_pages": max_pages,
            "forums": ["healthunlocked", "patient_info", "reddit_medical"],
            "task_id": task.id
        }
    )


@router.post("/incremental/{config_name}")
async def trigger_incremental(
    config_name: str,
    disease_terms: Optional[List[str]] = Query(None, description="Optional disease terms"),
    db: AsyncSession = Depends(get_db)
) -> ScrapeResponse:
    """Trigger incremental update for a specific forum"""
    
    # Validate config
    from sqlalchemy import text
    result = await db.execute(
        select(Source).where(
            text("config->>'scraper_config' = :config_name"),
            Source.is_active == True
        ).params(config_name=config_name)
    )
    source = result.scalar_one_or_none()
    
    if not source:
        raise HTTPException(
            status_code=404,
            detail=f"No active source found with config: {config_name}"
        )
    
    # Launch incremental task
    task = scrape_forum_incremental.delay(config_name, disease_terms)
    
    return ScrapeResponse(
        job_id=0,
        message=f"Incremental update started for {source.name}",
        status="started",
        details={
            "source": source.name,
            "last_crawled": source.last_crawled.isoformat() if source.last_crawled else None,
            "task_id": task.id
        }
    )


@router.post("/test/{config_name}")
async def test_scraper(
    config_name: str,
    test_url: Optional[str] = Query(None, description="Specific URL to test"),
    db: AsyncSession = Depends(get_db)
) -> Dict[str, Any]:
    """Test a forum scraper configuration"""
    
    # Validate config
    from sqlalchemy import text
    result = await db.execute(
        select(Source).where(
            text("config->>'scraper_config' = :config_name"),
            Source.is_active == True
        ).params(config_name=config_name)
    )
    source = result.scalar_one_or_none()
    
    if not source:
        raise HTTPException(
            status_code=404,
            detail=f"No active source found with config: {config_name}"
        )
    
    # Run test
    logger.info(f"Testing scraper for {source.name}")
    task = test_forum_scraper.delay(config_name, test_url)
    
    # Wait for result (tests should be quick)
    try:
        result = task.get(timeout=30)
        return {
            "source": source.name,
            "config_name": config_name,
            "test_results": result
        }
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Test failed: {str(e)}"
        )


@router.get("/stats")
async def get_web_scraping_stats(db: AsyncSession = Depends(get_db)) -> Dict[str, Any]:
    """Get statistics for web scraping sources"""
    
    # Get document counts per source
    stats_query = """
        SELECT 
            s.id,
            s.name,
            s.last_crawled,
            COUNT(d.id) as document_count,
            MAX(d.created_at) as last_document_date
        FROM sources s
        LEFT JOIN documents d ON d.source_id = s.id
        WHERE s.type = 'secondary'::source_type AND s.is_active = true
        GROUP BY s.id, s.name, s.last_crawled
        ORDER BY s.id
    """
    
    result = await db.execute(stats_query)
    stats = result.fetchall()
    
    return {
        "sources": [
            {
                "id": row[0],
                "name": row[1],
                "last_crawled": row[2].isoformat() if row[2] else None,
                "document_count": row[3],
                "last_document_date": row[4].isoformat() if row[4] else None
            }
            for row in stats
        ]
    }