from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta
from pydantic import BaseModel, Field
import json
from core.auth import get_current_admin
from core.database import get_pg_connection
from loguru import logger
from tasks.scrapers import (
    scrape_pubmed, scrape_clinicaltrials, scrape_reddit, scrape_faers,
    scrape_all_sources, scrape_incremental_all
)

router = APIRouter(prefix="/api/admin/jobs", tags=["admin-jobs"])

class JobResponse(BaseModel):
    id: int
    source_id: int
    source_name: Optional[str] = None
    status: str
    started_at: datetime
    completed_at: Optional[datetime] = None
    documents_found: Optional[int] = None
    documents_processed: Optional[int] = None
    errors: Optional[int] = None
    error_details: Optional[List[Dict[str, Any]]] = None
    config: Optional[Dict[str, Any]] = None
    created_at: datetime
    updated_at: Optional[datetime] = None  # Make it optional since crawl_jobs doesn't have this column
    duration_seconds: Optional[float] = None

class TriggerJobRequest(BaseModel):
    source_id: int
    disease_ids: List[int]
    options: Optional[Dict[str, Any]] = Field(default={})

class BulkJobRequest(BaseModel):
    source_ids: List[int] = Field(description="Source IDs to scrape, empty for all")
    disease_ids: List[int] = Field(description="Disease IDs to scrape, empty for all")
    job_type: str = Field(default="full", description="full or incremental")
    options: Optional[Dict[str, Any]] = Field(default={})

@router.get("/", response_model=List[JobResponse], dependencies=[Depends(get_current_admin)])
async def list_jobs(
    source_id: Optional[int] = None,
    status: Optional[str] = None,
    since: Optional[datetime] = None,
    limit: int = 100,
    offset: int = 0
) -> List[JobResponse]:
    """List crawl jobs with optional filtering"""
    async with get_pg_connection() as conn:
        query = """
            SELECT 
                cj.*,
                s.name as source_name,
                EXTRACT(EPOCH FROM (COALESCE(cj.completed_at, NOW()) - cj.started_at)) as duration_seconds
            FROM crawl_jobs cj
            JOIN sources s ON cj.source_id = s.id
            WHERE 1=1
        """
        params = []
        param_count = 0
        
        if source_id:
            param_count += 1
            query += f" AND cj.source_id = ${param_count}"
            params.append(source_id)
        
        if status:
            param_count += 1
            query += f" AND cj.status = ${param_count}"
            params.append(status)
        
        if since:
            param_count += 1
            query += f" AND cj.created_at >= ${param_count}"
            params.append(since)
        
        query += f" ORDER BY cj.created_at DESC LIMIT {limit} OFFSET {offset}"
        
        rows = await conn.fetch(query, *params)
        
        jobs = []
        for row in rows:
            job_dict = dict(row)
            # Handle JSONB fields
            if job_dict.get('config') and isinstance(job_dict['config'], str):
                job_dict['config'] = json.loads(job_dict['config'])
            if job_dict.get('error_details') and isinstance(job_dict['error_details'], str):
                job_dict['error_details'] = json.loads(job_dict['error_details'])
            jobs.append(JobResponse(**job_dict))
        
        return jobs

@router.get("/{job_id}", response_model=JobResponse, dependencies=[Depends(get_current_admin)])
async def get_job(job_id: int) -> JobResponse:
    """Get a specific job by ID"""
    async with get_pg_connection() as conn:
        row = await conn.fetchrow("""
            SELECT 
                cj.*,
                s.name as source_name,
                EXTRACT(EPOCH FROM (COALESCE(cj.completed_at, NOW()) - cj.started_at)) as duration_seconds
            FROM crawl_jobs cj
            JOIN sources s ON cj.source_id = s.id
            WHERE cj.id = $1
        """, job_id)
        
        if not row:
            raise HTTPException(status_code=404, detail="Job not found")
        
        job_dict = dict(row)
        # Handle JSONB fields
        if job_dict.get('config') and isinstance(job_dict['config'], str):
            job_dict['config'] = json.loads(job_dict['config'])
        if job_dict.get('error_details') and isinstance(job_dict['error_details'], str):
            job_dict['error_details'] = json.loads(job_dict['error_details'])
        
        return JobResponse(**job_dict)

@router.post("/trigger", dependencies=[Depends(get_current_admin)])
async def trigger_job(
    request: TriggerJobRequest,
    background_tasks: BackgroundTasks
) -> Dict[str, Any]:
    """Trigger a new scraping job for a specific source"""
    async with get_pg_connection() as conn:
        # Get source info
        source = await conn.fetchrow("SELECT * FROM sources WHERE id = $1", request.source_id)
        if not source:
            raise HTTPException(status_code=404, detail="Source not found")
        
        if source['status'] != 'active':
            raise HTTPException(status_code=400, detail="Source is not active")
        
        # Get disease names
        disease_rows = await conn.fetch("""
            SELECT id, name FROM disease_conditions WHERE id = ANY($1)
        """, request.disease_ids)
        
        if len(disease_rows) != len(request.disease_ids):
            raise HTTPException(status_code=400, detail="Some disease IDs not found")
        
        disease_names = [row['name'] for row in disease_rows]
        
        # Map source to task
        task_map = {
            "PubMed": scrape_pubmed,
            "ClinicalTrials.gov": scrape_clinicaltrials,
            "Reddit": scrape_reddit,
            "FDA FAERS": scrape_faers,
        }
        
        task = task_map.get(source['name'])
        if not task:
            raise HTTPException(
                status_code=400, 
                detail=f"No scraper task configured for source: {source['name']}"
            )
        
        # Trigger task
        result = task.delay(
            disease_ids=request.disease_ids,
            disease_names=disease_names,
            **request.options
        )
        
        return {
            "job_id": result.id,
            "source": source['name'],
            "diseases": disease_names,
            "status": "triggered"
        }

@router.post("/trigger-bulk", dependencies=[Depends(get_current_admin)])
async def trigger_bulk_jobs(
    request: BulkJobRequest,
    background_tasks: BackgroundTasks
) -> Dict[str, Any]:
    """Trigger scraping jobs for multiple sources"""
    async with get_pg_connection() as conn:
        # Get active sources
        if request.source_ids:
            sources = await conn.fetch("""
                SELECT id, name FROM sources 
                WHERE id = ANY($1) AND status = 'active'
            """, request.source_ids)
        else:
            sources = await conn.fetch("""
                SELECT id, name FROM sources WHERE status = 'active'
            """)
        
        if not sources:
            raise HTTPException(status_code=400, detail="No active sources found")
        
        # Get diseases
        if request.disease_ids:
            diseases = await conn.fetch("""
                SELECT id, name FROM disease_conditions WHERE id = ANY($1)
            """, request.disease_ids)
        else:
            diseases = await conn.fetch("SELECT id, name FROM disease_conditions")
        
        if not diseases:
            raise HTTPException(status_code=400, detail="No diseases found")
        
        disease_ids = [d['id'] for d in diseases]
        disease_names = [d['name'] for d in diseases]
        
        # Trigger appropriate task
        if request.job_type == "incremental":
            result = scrape_incremental_all.delay(
                disease_ids=disease_ids,
                disease_names=disease_names,
                **request.options
            )
        else:
            result = scrape_all_sources.delay(
                disease_ids=disease_ids,
                disease_names=disease_names,
                **request.options
            )
        
        return {
            "group_id": result.id,
            "job_type": request.job_type,
            "sources": [s['name'] for s in sources],
            "diseases": disease_names,
            "status": "triggered"
        }

@router.post("/{job_id}/cancel", dependencies=[Depends(get_current_admin)])
async def cancel_job(job_id: int) -> Dict[str, str]:
    """Cancel a running job"""
    async with get_pg_connection() as conn:
        # Check job exists and is running
        job = await conn.fetchrow("""
            SELECT id, status FROM crawl_jobs WHERE id = $1
        """, job_id)
        
        if not job:
            raise HTTPException(status_code=404, detail="Job not found")
        
        if job['status'] != 'running':
            raise HTTPException(status_code=400, detail=f"Job is not running (status: {job['status']})")
        
        # Update job status
        await conn.execute("""
            UPDATE crawl_jobs 
            SET status = 'cancelled', 
                completed_at = CURRENT_TIMESTAMP,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = $1
        """, job_id)
        
        # TODO: To properly cancel Celery tasks:
        # 1. Add 'task_id' column to crawl_jobs table to store Celery task ID
        # 2. When triggering a job, store the Celery task ID in the database
        # 3. Here, retrieve the task_id and use: celery_app.control.revoke(task_id, terminate=True)
        # Example:
        # from tasks import celery_app
        # if job['task_id']:
        #     celery_app.control.revoke(job['task_id'], terminate=True)
        
        logger.warning(f"Job {job_id} marked as cancelled, but Celery task may still be running")
        
        return {"message": "Job cancelled successfully (Note: Celery task may continue running)"}

@router.get("/stats/summary", dependencies=[Depends(get_current_admin)])
async def get_job_stats(
    days: int = 7
) -> Dict[str, Any]:
    """Get job statistics summary"""
    async with get_pg_connection() as conn:
        since_date = datetime.now() - timedelta(days=days)
        
        # Overall stats
        overall = await conn.fetchrow("""
            SELECT 
                COUNT(*) as total_jobs,
                COUNT(*) FILTER (WHERE status = 'completed') as completed,
                COUNT(*) FILTER (WHERE status = 'failed') as failed,
                COUNT(*) FILTER (WHERE status = 'running') as running,
                COUNT(*) FILTER (WHERE status = 'cancelled') as cancelled,
                SUM(documents_found) as total_documents_found,
                SUM(documents_processed) as total_documents_processed,
                AVG(EXTRACT(EPOCH FROM (completed_at - started_at))) FILTER (WHERE completed_at IS NOT NULL) as avg_duration_seconds
            FROM crawl_jobs
            WHERE created_at >= $1
        """, since_date)
        
        # Stats by source
        by_source = await conn.fetch("""
            SELECT 
                s.name as source_name,
                COUNT(*) as job_count,
                COUNT(*) FILTER (WHERE cj.status = 'completed') as completed,
                COUNT(*) FILTER (WHERE cj.status = 'failed') as failed,
                SUM(cj.documents_found) as documents_found,
                SUM(cj.documents_processed) as documents_processed,
                AVG(EXTRACT(EPOCH FROM (cj.completed_at - cj.started_at))) FILTER (WHERE cj.completed_at IS NOT NULL) as avg_duration
            FROM crawl_jobs cj
            JOIN sources s ON cj.source_id = s.id
            WHERE cj.created_at >= $1
            GROUP BY s.id, s.name
            ORDER BY job_count DESC
        """, since_date)
        
        # Daily trends
        daily_trends = await conn.fetch("""
            SELECT 
                DATE(created_at) as date,
                COUNT(*) as jobs,
                COUNT(*) FILTER (WHERE status = 'completed') as completed,
                SUM(documents_processed) as documents
            FROM crawl_jobs
            WHERE created_at >= $1
            GROUP BY DATE(created_at)
            ORDER BY date DESC
        """, since_date)
        
        # Recent errors
        recent_errors = await conn.fetch("""
            SELECT 
                cj.id,
                s.name as source_name,
                cj.started_at,
                cj.errors,
                cj.error_details::text as error_sample
            FROM crawl_jobs cj
            JOIN sources s ON cj.source_id = s.id
            WHERE cj.status = 'failed' AND cj.created_at >= $1
            ORDER BY cj.created_at DESC
            LIMIT 10
        """, since_date)
        
        return {
            "period_days": days,
            "overall": dict(overall),
            "by_source": [dict(row) for row in by_source],
            "daily_trends": [dict(row) for row in daily_trends],
            "recent_errors": [dict(row) for row in recent_errors]
        }