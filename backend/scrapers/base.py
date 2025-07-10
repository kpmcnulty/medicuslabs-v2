import asyncio
from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime
import httpx
from loguru import logger
import json
import os
from pathlib import Path
import hashlib

from core.config import settings
from core.database import get_pg_connection
from models.schemas import DocumentCreate, CrawlJobUpdate

class RateLimiter:
    """Simple rate limiter for API calls"""
    def __init__(self, max_per_second: float):
        self.max_per_second = max_per_second
        self.min_interval = 1.0 / max_per_second
        self.last_request = 0.0
        self._lock = asyncio.Lock()
    
    async def acquire(self):
        async with self._lock:
            current = asyncio.get_event_loop().time()
            time_since_last = current - self.last_request
            if time_since_last < self.min_interval:
                await asyncio.sleep(self.min_interval - time_since_last)
            self.last_request = asyncio.get_event_loop().time()

class BaseScraper(ABC):
    """Base class for all scrapers"""
    
    def __init__(self, source_id: int, source_name: str, rate_limit: float = 1.0):
        self.source_id = source_id
        self.source_name = source_name
        self.rate_limiter = RateLimiter(rate_limit)
        self.client = httpx.AsyncClient(timeout=30.0)
        self.job_id: Optional[int] = None
        self.errors: List[Dict[str, Any]] = []
        
    async def __aenter__(self):
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.client.aclose()
    
    @abstractmethod
    async def search(self, disease_term: str, **kwargs) -> List[Dict[str, Any]]:
        """Search for documents related to a disease term"""
        pass
    
    @abstractmethod
    async def fetch_details(self, external_id: str) -> Dict[str, Any]:
        """Fetch detailed information for a specific document"""
        pass
    
    @abstractmethod
    def extract_document_data(self, raw_data: Dict[str, Any]) -> Tuple[DocumentCreate, Optional[datetime]]:
        """Extract and transform raw data into DocumentCreate schema with source update timestamp"""
        pass
    
    async def start_job(self, config: Dict[str, Any] = {}) -> int:
        """Create a new crawl job"""
        async with get_pg_connection() as conn:
            result = await conn.fetchrow(
                """
                INSERT INTO crawl_jobs (source_id, status, started_at, config)
                VALUES ($1, 'running', $2, $3)
                RETURNING id
                """,
                self.source_id,
                datetime.now(),
                json.dumps(config)
            )
            self.job_id = result['id']
            logger.info(f"Started crawl job {self.job_id} for {self.source_name}")
            return self.job_id
    
    async def update_source_state(self, last_crawled_id: str = None, crawl_state: Dict = None):
        """Update source crawl state for incremental updates"""
        async with get_pg_connection() as conn:
            if last_crawled_id:
                await conn.execute(
                    """
                    UPDATE sources 
                    SET last_crawled = CURRENT_TIMESTAMP,
                        last_crawled_id = $2,
                        crawl_state = COALESCE($3, crawl_state)
                    WHERE id = $1
                    """,
                    self.source_id,
                    last_crawled_id,
                    json.dumps(crawl_state) if crawl_state else None
                )
            elif crawl_state:
                await conn.execute(
                    """
                    UPDATE sources 
                    SET crawl_state = $2
                    WHERE id = $1
                    """,
                    self.source_id,
                    json.dumps(crawl_state)
                )
    
    async def get_source_state(self) -> Dict[str, Any]:
        """Get source crawl state"""
        async with get_pg_connection() as conn:
            result = await conn.fetchrow(
                """
                SELECT last_crawled, last_crawled_id, crawl_state
                FROM sources
                WHERE id = $1
                """,
                self.source_id
            )
            if result:
                return {
                    'last_crawled': result['last_crawled'],
                    'last_crawled_id': result['last_crawled_id'],
                    'crawl_state': result['crawl_state'] or {}
                }
            return {}
    
    async def update_job(self, update: CrawlJobUpdate):
        """Update crawl job status"""
        if not self.job_id:
            return
            
        async with get_pg_connection() as conn:
            query_parts = []
            values = [self.job_id]
            param_count = 1
            
            if update.status:
                param_count += 1
                query_parts.append(f"status = ${param_count}")
                values.append(update.status)
                
                if update.status in ['completed', 'failed']:
                    param_count += 1
                    query_parts.append(f"completed_at = ${param_count}")
                    values.append(datetime.now())
            
            if update.documents_found is not None:
                param_count += 1
                query_parts.append(f"documents_found = ${param_count}")
                values.append(update.documents_found)
            
            if update.documents_processed is not None:
                param_count += 1
                query_parts.append(f"documents_processed = ${param_count}")
                values.append(update.documents_processed)
            
            if update.errors is not None:
                param_count += 1
                query_parts.append(f"errors = ${param_count}")
                values.append(update.errors)
            
            if update.error_details is not None:
                param_count += 1
                query_parts.append(f"error_details = ${param_count}")
                values.append(json.dumps(update.error_details))
            
            if query_parts:
                query = f"""
                    UPDATE crawl_jobs 
                    SET {', '.join(query_parts)}
                    WHERE id = $1
                """
                await conn.execute(query, *values)
    
    async def get_existing_document(self, external_id: str) -> Optional[Dict[str, Any]]:
        """Get existing document if it exists"""
        async with get_pg_connection() as conn:
            result = await conn.fetchrow(
                """
                SELECT id, source_updated_at, metadata, update_count
                FROM documents 
                WHERE source_id = $1 AND external_id = $2
                """,
                self.source_id,
                external_id
            )
            return dict(result) if result else None
    
    async def save_document(self, document: DocumentCreate, source_updated_at: Optional[datetime] = None) -> Optional[int]:
        """Save or update document in database"""
        try:
            # Check if document exists
            existing = await self.get_existing_document(document.external_id)
            
            if existing:
                # Check if update is needed
                if source_updated_at and existing.get('source_updated_at'):
                    if source_updated_at <= existing['source_updated_at']:
                        logger.debug(f"Document {document.external_id} is up to date, skipping")
                        # Update last_checked_at
                        await self._update_last_checked(existing['id'])
                        return existing['id']
                
                # Update existing document
                return await self._update_document(existing['id'], document, source_updated_at)
            
            
            # Insert document (skip raw file saving for now)
            async with get_pg_connection() as conn:
                result = await conn.fetchrow(
                    """
                    INSERT INTO documents (
                        source_id, external_id, url, title, content, 
                        summary, metadata, scraped_at, status,
                        source_updated_at, last_checked_at
                    ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, 'pending', $9, CURRENT_TIMESTAMP)
                    RETURNING id
                    """,
                    document.source_id,
                    document.external_id,
                    document.url,
                    document.title,
                    document.content,
                    document.summary,
                    json.dumps(document.metadata),
                    document.scraped_at,
                    source_updated_at or datetime.now()
                )
                doc_id = result['id']
                logger.info(f"Saved document {document.external_id} with ID {doc_id}")
                return doc_id
                
        except Exception as e:
            logger.error(f"Error saving document {document.external_id}: {e}")
            self.errors.append({
                "external_id": document.external_id,
                "error": str(e),
                "timestamp": datetime.now().isoformat()
            })
            return None
    
    async def _update_document(self, doc_id: int, document: DocumentCreate, source_updated_at: Optional[datetime] = None) -> int:
        """Update existing document"""
        try:
            async with get_pg_connection() as conn:
                await conn.execute(
                    """
                    UPDATE documents SET
                        title = $2,
                        content = $3,
                        summary = $4,
                        metadata = $5,
                        updated_at = CURRENT_TIMESTAMP,
                        last_checked_at = CURRENT_TIMESTAMP,
                        source_updated_at = $6,
                        update_count = COALESCE(update_count, 0) + 1
                    WHERE id = $1
                    """,
                    doc_id,
                    document.title,
                    document.content,
                    document.summary,
                    json.dumps(document.metadata),
                    source_updated_at or datetime.now()
                )
                logger.info(f"Updated document {document.external_id} (ID: {doc_id})")
                return doc_id
        except Exception as e:
            logger.error(f"Error updating document {document.external_id}: {e}")
            raise
    
    async def _update_last_checked(self, doc_id: int):
        """Update last_checked_at timestamp"""
        async with get_pg_connection() as conn:
            await conn.execute(
                "UPDATE documents SET last_checked_at = CURRENT_TIMESTAMP WHERE id = $1",
                doc_id
            )
    
    async def save_raw_file(self, external_id: str, data: Dict[str, Any]) -> str:
        """Save raw data to file"""
        # Create directory structure
        date = datetime.now()
        subdir = self.source_name.lower().replace('.', '').replace(' ', '_')
        dir_path = Path(settings.raw_data_path) / subdir / f"{date.year}" / f"{date.month:02d}"
        dir_path.mkdir(parents=True, exist_ok=True)
        
        # Save file
        filename = f"{external_id.replace('/', '_')}.json"
        file_path = dir_path / filename
        
        with open(file_path, 'w') as f:
            json.dump(data, f, indent=2, default=str)
        
        return str(file_path)
    
    async def make_request(self, url: str, params: Optional[Dict] = None) -> Dict[str, Any]:
        """Make rate-limited HTTP request"""
        await self.rate_limiter.acquire()
        
        try:
            response = await self.client.get(url, params=params)
            response.raise_for_status()
            return response.json()
        except httpx.HTTPError as e:
            logger.error(f"HTTP error for {url}: {e}")
            raise
        except Exception as e:
            logger.error(f"Error making request to {url}: {e}")
            raise
    
    async def scrape_incremental(self, disease_terms: List[str], **kwargs) -> Dict[str, Any]:
        """Incremental scraping - only get new/updated documents"""
        # Get last crawl state
        state = await self.get_source_state()
        last_crawled = state.get('last_crawled')
        
        if last_crawled:
            kwargs['since_date'] = last_crawled
            logger.info(f"Running incremental update since {last_crawled}")
        else:
            logger.info("No previous crawl found, running full scrape")
        
        return await self.scrape(disease_terms, **kwargs)
    
    async def scrape(self, disease_terms: List[str], **kwargs) -> Dict[str, Any]:
        """Main scraping method"""
        await self.start_job({"disease_terms": disease_terms, **kwargs})
        
        total_found = 0
        total_processed = 0
        
        try:
            for term in disease_terms:
                logger.info(f"Searching for '{term}' in {self.source_name}")
                
                # Search for documents
                results = await self.search(term, **kwargs)
                total_found += len(results)
                
                # Process each result
                for result in results:
                    try:
                        # Extract basic data
                        document, source_updated_at = self.extract_document_data(result)
                        
                        # Save to database
                        doc_id = await self.save_document(document, source_updated_at)
                        if doc_id:
                            total_processed += 1
                            # Update last crawled ID
                            await self.update_source_state(last_crawled_id=document.external_id)
                        
                        # Update job progress
                        if total_processed % 10 == 0:
                            await self.update_job(CrawlJobUpdate(
                                documents_found=total_found,
                                documents_processed=total_processed
                            ))
                            
                    except Exception as e:
                        logger.error(f"Error processing document: {e}")
                        self.errors.append({
                            "data": str(result)[:200],
                            "error": str(e),
                            "timestamp": datetime.now().isoformat()
                        })
            
            # Final job update
            await self.update_job(CrawlJobUpdate(
                status="completed",
                documents_found=total_found,
                documents_processed=total_processed,
                errors=len(self.errors),
                error_details=self.errors
            ))
            
            logger.info(f"Scraping completed: {total_processed}/{total_found} documents processed")
            
            return {
                "job_id": self.job_id,
                "documents_found": total_found,
                "documents_processed": total_processed,
                "errors": len(self.errors)
            }
            
        except Exception as e:
            logger.error(f"Fatal error during scraping: {e}")
            await self.update_job(CrawlJobUpdate(
                status="failed",
                errors=len(self.errors) + 1,
                error_details=self.errors + [{
                    "error": str(e),
                    "timestamp": datetime.now().isoformat()
                }]
            ))
            raise