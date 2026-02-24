from fastapi import APIRouter, Depends, HTTPException, status
from typing import List, Dict, Any, Optional
from datetime import datetime
from pydantic import BaseModel, Field
import json
from core.auth import get_current_admin
from core.database import get_pg_connection
from loguru import logger

router = APIRouter(prefix="/api/admin/sources", tags=["admin-sources"])

class SourceBase(BaseModel):
    name: str
    category: str = Field(..., description="publications, trials, or community")
    base_url: Optional[str] = None
    scraper_type: Optional[str] = None
    rate_limit: Optional[int] = Field(default=10)
    is_active: bool = Field(default=True)
    config: Optional[Dict[str, Any]] = Field(default={})
    association_method: str = Field(default='search', description="linked or search")
    disease_ids: Optional[List[int]] = Field(default=[], description="For linked sources only")

class SourceCreate(SourceBase):
    pass

class SourceUpdate(BaseModel):
    name: Optional[str] = None
    category: Optional[str] = None
    base_url: Optional[str] = None
    scraper_type: Optional[str] = None
    rate_limit: Optional[int] = None
    is_active: Optional[bool] = None
    config: Optional[Dict[str, Any]] = None
    association_method: Optional[str] = None
    disease_ids: Optional[List[int]] = None

class SourceResponse(SourceBase):
    id: int
    last_crawled: Optional[datetime] = None
    last_crawled_id: Optional[str] = None
    crawl_state: Optional[Dict[str, Any]] = None
    created_at: datetime
    updated_at: datetime
    document_count: Optional[int] = None
    recent_job_count: Optional[int] = None
    disease_names: Optional[List[str]] = Field(default=[], description="Names of linked diseases for fixed sources")

@router.get("/", response_model=List[SourceResponse], dependencies=[Depends(get_current_admin)])
async def list_sources(
    is_active: Optional[bool] = None,
    category: Optional[str] = None
) -> List[SourceResponse]:
    """List all sources with optional filtering"""
    async with get_pg_connection() as conn:
        query = """
            SELECT 
                s.*,
                COUNT(DISTINCT d.id) as document_count,
                COUNT(DISTINCT cj.id) FILTER (WHERE cj.created_at > NOW() - INTERVAL '7 days') as recent_job_count,
                COALESCE(
                    array_agg(DISTINCT dis.name) FILTER (WHERE dis.name IS NOT NULL), 
                    ARRAY[]::text[]
                ) as disease_names,
                COALESCE(
                    array_agg(DISTINCT dis.id) FILTER (WHERE dis.id IS NOT NULL), 
                    ARRAY[]::integer[]
                ) as disease_ids
            FROM sources s
            LEFT JOIN documents d ON s.id = d.source_id
            LEFT JOIN crawl_jobs cj ON s.id = cj.source_id
            LEFT JOIN source_diseases sd ON s.id = sd.source_id
            LEFT JOIN diseases dis ON sd.disease_id = dis.id
            WHERE 1=1
        """
        params = []
        param_count = 0
        
        if is_active is not None:
            param_count += 1
            query += f" AND s.is_active = ${param_count}"
            params.append(is_active)
        
        if category:
            param_count += 1
            query += f" AND s.category = ${param_count}"
            params.append(category)
        
        query += " GROUP BY s.id ORDER BY s.name"
        
        rows = await conn.fetch(query, *params)
        
        sources = []
        for row in rows:
            source_dict = dict(row)
            # Handle JSONB fields
            if source_dict.get('config') and isinstance(source_dict['config'], str):
                source_dict['config'] = json.loads(source_dict['config'])
            if source_dict.get('crawl_state') and isinstance(source_dict['crawl_state'], str):
                source_dict['crawl_state'] = json.loads(source_dict['crawl_state'])
            sources.append(SourceResponse(**source_dict))
        
        return sources

@router.get("/{source_id}", response_model=SourceResponse, dependencies=[Depends(get_current_admin)])
async def get_source(source_id: int) -> SourceResponse:
    """Get a specific source by ID"""
    async with get_pg_connection() as conn:
        row = await conn.fetchrow("""
            SELECT 
                s.*,
                COUNT(DISTINCT d.id) as document_count,
                COUNT(DISTINCT cj.id) FILTER (WHERE cj.created_at > NOW() - INTERVAL '7 days') as recent_job_count,
                COALESCE(
                    array_agg(DISTINCT dis.name) FILTER (WHERE dis.name IS NOT NULL), 
                    ARRAY[]::text[]
                ) as disease_names,
                COALESCE(
                    array_agg(DISTINCT dis.id) FILTER (WHERE dis.id IS NOT NULL), 
                    ARRAY[]::integer[]
                ) as disease_ids
            FROM sources s
            LEFT JOIN documents d ON s.id = d.source_id
            LEFT JOIN crawl_jobs cj ON s.id = cj.source_id
            LEFT JOIN source_diseases sd ON s.id = sd.source_id
            LEFT JOIN diseases dis ON sd.disease_id = dis.id
            WHERE s.id = $1
            GROUP BY s.id
        """, source_id)
        
        if not row:
            raise HTTPException(status_code=404, detail="Source not found")
        
        source_dict = dict(row)
        # Handle JSONB fields
        if source_dict.get('config') and isinstance(source_dict['config'], str):
            source_dict['config'] = json.loads(source_dict['config'])
        if source_dict.get('default_config') and isinstance(source_dict['default_config'], str):
            source_dict['default_config'] = json.loads(source_dict['default_config'])
        if source_dict.get('crawl_state') and isinstance(source_dict['crawl_state'], str):
            source_dict['crawl_state'] = json.loads(source_dict['crawl_state'])
        
        return SourceResponse(**source_dict)

@router.post("/", response_model=SourceResponse, dependencies=[Depends(get_current_admin)])
async def create_source(source: SourceCreate) -> SourceResponse:
    """Create a new source"""
    async with get_pg_connection() as conn:
        # Check if source name already exists
        existing = await conn.fetchval("SELECT id FROM sources WHERE name = $1", source.name)
        if existing:
            raise HTTPException(status_code=400, detail="Source with this name already exists")
        
        # Insert new source
        async with conn.transaction():
            row = await conn.fetchrow("""
                INSERT INTO sources (name, category, base_url, scraper_type, rate_limit, is_active, config, association_method)
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
                RETURNING *
            """, 
                source.name, 
                source.category, 
                source.base_url, 
                source.scraper_type, 
                source.rate_limit,
                source.is_active,
                json.dumps(source.config or {}),
                source.association_method
            )
            
            source_id = row['id']
            
            # If linked source, insert disease associations
            if source.association_method == 'linked' and source.disease_ids:
                for disease_id in source.disease_ids:
                    await conn.execute("""
                        INSERT INTO source_diseases (source_id, disease_id)
                        VALUES ($1, $2)
                    """, source_id, disease_id)
        
        source_dict = dict(row)
        source_dict['document_count'] = 0
        source_dict['recent_job_count'] = 0
        source_dict['disease_ids'] = source.disease_ids or []
        source_dict['disease_names'] = []
        
        # Get disease names if linked source
        if source.association_method == 'linked' and source.disease_ids:
            disease_rows = await conn.fetch("""
                SELECT name FROM diseases WHERE id = ANY($1)
            """, source.disease_ids)
            source_dict['disease_names'] = [row['name'] for row in disease_rows]
        
        return SourceResponse(**source_dict)

@router.patch("/{source_id}", response_model=SourceResponse, dependencies=[Depends(get_current_admin)])
async def update_source(source_id: int, source_update: SourceUpdate) -> SourceResponse:
    """Update a source"""
    async with get_pg_connection() as conn:
        # Check if source exists
        existing = await conn.fetchrow("SELECT * FROM sources WHERE id = $1", source_id)
        if not existing:
            raise HTTPException(status_code=404, detail="Source not found")
        
        async with conn.transaction():
            # Build update query dynamically
            update_fields = []
            params = [source_id]
            param_count = 1
            
            update_dict = source_update.dict(exclude_unset=True)
            disease_ids = update_dict.pop('disease_ids', None)
            
            for field, value in update_dict.items():
                param_count += 1
                if field == 'config':
                    update_fields.append(f"{field} = ${param_count}::jsonb")
                    params.append(json.dumps(value))
                else:
                    update_fields.append(f"{field} = ${param_count}")
                    params.append(value)
            
            if update_fields:
                update_fields.append("updated_at = CURRENT_TIMESTAMP")
                query = f"""
                    UPDATE sources 
                    SET {', '.join(update_fields)}
                    WHERE id = $1
                    RETURNING *
                """
                row = await conn.fetchrow(query, *params)
            else:
                row = existing
            
            # Update disease associations if provided
            if disease_ids is not None:
                # Delete existing associations
                await conn.execute("DELETE FROM source_diseases WHERE source_id = $1", source_id)
                
                # Insert new associations
                for disease_id in disease_ids:
                    await conn.execute("""
                        INSERT INTO source_diseases (source_id, disease_id)
                        VALUES ($1, $2)
                    """, source_id, disease_id)
        
        # Get counts
        counts = await conn.fetchrow("""
            SELECT 
                COUNT(DISTINCT d.id) as document_count,
                COUNT(DISTINCT cj.id) FILTER (WHERE cj.created_at > NOW() - INTERVAL '7 days') as recent_job_count
            FROM sources s
            LEFT JOIN documents d ON s.id = d.source_id
            LEFT JOIN crawl_jobs cj ON s.id = cj.source_id
            WHERE s.id = $1
        """, source_id)
        
        # Get disease associations
        disease_rows = await conn.fetch("""
            SELECT d.id, d.name 
            FROM diseases d
            JOIN source_diseases sd ON d.id = sd.disease_id
            WHERE sd.source_id = $1
        """, source_id)
        
        source_dict = dict(row)
        source_dict['document_count'] = counts['document_count']
        source_dict['recent_job_count'] = counts['recent_job_count']
        source_dict['disease_ids'] = [row['id'] for row in disease_rows]
        source_dict['disease_names'] = [row['name'] for row in disease_rows]
        
        # Handle JSONB fields
        if source_dict.get('config') and isinstance(source_dict['config'], str):
            source_dict['config'] = json.loads(source_dict['config'])
        if source_dict.get('default_config') and isinstance(source_dict['default_config'], str):
            source_dict['default_config'] = json.loads(source_dict['default_config'])
        if source_dict.get('crawl_state') and isinstance(source_dict['crawl_state'], str):
            source_dict['crawl_state'] = json.loads(source_dict['crawl_state'])
        
        return SourceResponse(**source_dict)

@router.delete("/{source_id}", dependencies=[Depends(get_current_admin)])
async def delete_source(source_id: int) -> Dict[str, str]:
    """Delete a source (soft delete by setting is_active to false)"""
    async with get_pg_connection() as conn:
        # Check if source exists
        existing = await conn.fetchval("SELECT id FROM sources WHERE id = $1", source_id)
        if not existing:
            raise HTTPException(status_code=404, detail="Source not found")
        
        # Check if source has documents
        doc_count = await conn.fetchval("SELECT COUNT(*) FROM documents WHERE source_id = $1", source_id)
        if doc_count > 0:
            # Soft delete - just set is_active to false
            await conn.execute("""
                UPDATE sources 
                SET is_active = false, updated_at = CURRENT_TIMESTAMP
                WHERE id = $1
            """, source_id)
            return {"message": f"Source deactivated (has {doc_count} documents)"}
        else:
            # Hard delete if no documents
            await conn.execute("DELETE FROM sources WHERE id = $1", source_id)
            return {"message": "Source deleted"}

@router.post("/{source_id}/test-connection", dependencies=[Depends(get_current_admin)])
async def test_source_connection(source_id: int) -> Dict[str, Any]:
    """Test connection to a source"""
    async with get_pg_connection() as conn:
        source = await conn.fetchrow("SELECT * FROM sources WHERE id = $1", source_id)
        if not source:
            raise HTTPException(status_code=404, detail="Source not found")
        
        # TODO: Implement actual connection testing based on source category
        # For now, return mock response
        return {
            "status": "success",
            "message": f"Connection test for {source['name']} would be implemented here",
            "details": {
                "source_category": source['category'],
                "base_url": source['base_url'],
                "has_credentials": bool(source.get('config'))
            }
        }

class TriggerScrapeRequest(BaseModel):
    disease_ids: Optional[List[int]] = None
    options: Optional[Dict[str, Any]] = None

@router.post("/{source_id}/trigger-scrape", dependencies=[Depends(get_current_admin)])
async def trigger_source_scrape(
    source_id: int,
    request: TriggerScrapeRequest
) -> Dict[str, Any]:
    """Trigger a scraping job for a specific source"""
    async with get_pg_connection() as conn:
        # Get source details
        source = await conn.fetchrow("""
            SELECT id, name, scraper_type, association_method, is_active
            FROM sources 
            WHERE id = $1
        """, source_id)
        
        if not source:
            raise HTTPException(status_code=404, detail="Source not found")
        
        if not source['is_active']:
            raise HTTPException(status_code=400, detail="Source is not active")
        
        # For linked sources, get their linked diseases
        if source['association_method'] == 'linked':
            linked = await conn.fetch("""
                SELECT sd.disease_id, d.name as disease_name
                FROM source_diseases sd
                JOIN diseases d ON sd.disease_id = d.id
                WHERE sd.source_id = $1
            """, source_id)
            
            if not linked:
                raise HTTPException(
                    status_code=400,
                    detail="Linked source has no linked diseases"
                )
            
            # Use linked diseases if no specific ones requested
            if not request.disease_ids:
                disease_ids = [row['disease_id'] for row in linked]
                disease_names = [row['disease_name'] for row in linked]
            else:
                # Filter to only linked diseases
                linked_ids = {row['disease_id'] for row in linked}
                valid_ids = [did for did in request.disease_ids if did in linked_ids]
                if not valid_ids:
                    raise HTTPException(
                        status_code=400,
                        detail="Requested diseases not linked to this source"
                    )
                disease_ids = valid_ids
                disease_names = [row['disease_name'] for row in linked if row['disease_id'] in valid_ids]
        else:
            # For search sources, require disease_ids
            if not request.disease_ids:
                raise HTTPException(
                    status_code=400,
                    detail="Disease IDs required for search-based sources"
                )
            
            # Get disease names
            diseases = await conn.fetch("""
                SELECT id, name FROM diseases WHERE id = ANY($1)
            """, request.disease_ids)
            
            if len(diseases) != len(request.disease_ids):
                raise HTTPException(
                    status_code=400,
                    detail="One or more disease IDs not found"
                )
            
            disease_names = [row['name'] for row in diseases]
        
        # Create crawl job
        job_id = await conn.fetchval("""
            INSERT INTO crawl_jobs (source_id, status, started_at, config)
            VALUES ($1, 'pending', CURRENT_TIMESTAMP, $2)
            RETURNING id
        """, 
            source_id,
            json.dumps({
                "disease_ids": disease_ids,
                "disease_names": disease_names,
                **(request.options or {})
            })
        )
        
        # Import scraper classes directly
        from scrapers.clinicaltrials import ClinicalTrialsScraper
        from scrapers.pubmed import PubMedScraper
        from scrapers.reddit import RedditScraper
        from scrapers.faers import FAERSScraper
        
        scraper_map = {
            'reddit_scraper': RedditScraper,
            'pubmed_api': PubMedScraper,
            'clinicaltrials_api': ClinicalTrialsScraper,
            'faers_api': FAERSScraper,
        }
        
        scraper_class = scraper_map.get(source['scraper_type'])
        if not scraper_class:
            await conn.execute("""
                UPDATE crawl_jobs 
                SET status = 'failed', 
                    completed_at = CURRENT_TIMESTAMP,
                    error_details = $2
                WHERE id = $1
            """, job_id, json.dumps([{
                "error": f"No scraper for type: {source['scraper_type']}",
                "timestamp": datetime.now().isoformat()
            }]))
            raise HTTPException(status_code=400, detail=f"No scraper for type: {source['scraper_type']}")
        
        # Run scraper in background
        from api.scrapers import run_scraper_task
        import asyncio
        asyncio.create_task(run_scraper_task(
            scraper_class=scraper_class,
            disease_names=disease_names,
            job_id=job_id,
            source_id=source_id,
            source_name=source['name'],
            options=request.options or {}
        ))
        
        return {
            "job_id": job_id,
            "message": f"Scraping job started for {source['name']}",
            "details": {
                "source_id": source_id,
                "source_name": source['name'],
                "association_method": source['association_method'],
                "disease_count": len(disease_ids),
                "diseases": disease_names[:5]
            }
        }