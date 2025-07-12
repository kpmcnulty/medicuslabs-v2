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
    type: str = Field(..., description="publication, clinical_trial, or forum")
    url: Optional[str] = None
    description: Optional[str] = None
    status: str = Field(default="active", description="active or inactive")
    config: Optional[Dict[str, Any]] = Field(default={})
    default_config: Optional[Dict[str, Any]] = Field(default={})

class SourceCreate(SourceBase):
    pass

class SourceUpdate(BaseModel):
    name: Optional[str] = None
    type: Optional[str] = None
    url: Optional[str] = None
    description: Optional[str] = None
    status: Optional[str] = None
    config: Optional[Dict[str, Any]] = None
    default_config: Optional[Dict[str, Any]] = None

class SourceResponse(SourceBase):
    id: int
    last_crawled: Optional[datetime] = None
    last_crawled_id: Optional[str] = None
    crawl_state: Optional[Dict[str, Any]] = None
    created_at: datetime
    updated_at: datetime
    document_count: Optional[int] = None
    recent_job_count: Optional[int] = None

@router.get("/", response_model=List[SourceResponse], dependencies=[Depends(get_current_admin)])
async def list_sources(
    status: Optional[str] = None,
    type: Optional[str] = None
) -> List[SourceResponse]:
    """List all sources with optional filtering"""
    async with get_pg_connection() as conn:
        query = """
            SELECT 
                s.*,
                COUNT(DISTINCT d.id) as document_count,
                COUNT(DISTINCT cj.id) FILTER (WHERE cj.created_at > NOW() - INTERVAL '7 days') as recent_job_count
            FROM sources s
            LEFT JOIN documents d ON s.id = d.source_id
            LEFT JOIN crawl_jobs cj ON s.id = cj.source_id
            WHERE 1=1
        """
        params = []
        param_count = 0
        
        if status:
            param_count += 1
            query += f" AND s.status = ${param_count}"
            params.append(status)
        
        if type:
            param_count += 1
            query += f" AND s.type = ${param_count}"
            params.append(type)
        
        query += " GROUP BY s.id ORDER BY s.name"
        
        rows = await conn.fetch(query, *params)
        
        sources = []
        for row in rows:
            source_dict = dict(row)
            # Handle JSONB fields
            if source_dict.get('config') and isinstance(source_dict['config'], str):
                source_dict['config'] = json.loads(source_dict['config'])
            if source_dict.get('default_config') and isinstance(source_dict['default_config'], str):
                source_dict['default_config'] = json.loads(source_dict['default_config'])
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
                COUNT(DISTINCT cj.id) FILTER (WHERE cj.created_at > NOW() - INTERVAL '7 days') as recent_job_count
            FROM sources s
            LEFT JOIN documents d ON s.id = d.source_id
            LEFT JOIN crawl_jobs cj ON s.id = cj.source_id
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
        row = await conn.fetchrow("""
            INSERT INTO sources (name, type, url, description, status, config, default_config)
            VALUES ($1, $2, $3, $4, $5, $6, $7)
            RETURNING *
        """, 
            source.name, 
            source.type, 
            source.url, 
            source.description, 
            source.status,
            json.dumps(source.config or {}),
            json.dumps(source.default_config or {})
        )
        
        source_dict = dict(row)
        source_dict['document_count'] = 0
        source_dict['recent_job_count'] = 0
        
        return SourceResponse(**source_dict)

@router.patch("/{source_id}", response_model=SourceResponse, dependencies=[Depends(get_current_admin)])
async def update_source(source_id: int, source_update: SourceUpdate) -> SourceResponse:
    """Update a source"""
    async with get_pg_connection() as conn:
        # Check if source exists
        existing = await conn.fetchrow("SELECT * FROM sources WHERE id = $1", source_id)
        if not existing:
            raise HTTPException(status_code=404, detail="Source not found")
        
        # Build update query dynamically
        update_fields = []
        params = [source_id]
        param_count = 1
        
        update_dict = source_update.dict(exclude_unset=True)
        for field, value in update_dict.items():
            param_count += 1
            if field in ['config', 'default_config']:
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
        
        source_dict = dict(row)
        source_dict['document_count'] = counts['document_count']
        source_dict['recent_job_count'] = counts['recent_job_count']
        
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
    """Delete a source (soft delete by setting status to inactive)"""
    async with get_pg_connection() as conn:
        # Check if source exists
        existing = await conn.fetchval("SELECT id FROM sources WHERE id = $1", source_id)
        if not existing:
            raise HTTPException(status_code=404, detail="Source not found")
        
        # Check if source has documents
        doc_count = await conn.fetchval("SELECT COUNT(*) FROM documents WHERE source_id = $1", source_id)
        if doc_count > 0:
            # Soft delete - just set status to inactive
            await conn.execute("""
                UPDATE sources 
                SET status = 'inactive', updated_at = CURRENT_TIMESTAMP
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
        
        # TODO: Implement actual connection testing based on source type
        # For now, return mock response
        return {
            "status": "success",
            "message": f"Connection test for {source['name']} would be implemented here",
            "details": {
                "source_type": source['type'],
                "url": source['url'],
                "has_credentials": bool(source.get('config'))
            }
        }