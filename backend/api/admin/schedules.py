from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks
from typing import List, Dict, Any, Optional
from datetime import datetime
from pydantic import BaseModel, Field
from celery.schedules import crontab
from core.auth import get_current_admin
from tasks import celery_app
from tasks.scheduled import (
    daily_incremental_update, weekly_full_check, 
    check_running_jobs, scrape_specific_disease
)
from loguru import logger

router = APIRouter(prefix="/api/admin/schedules", tags=["admin-schedules"])

class ScheduleBase(BaseModel):
    name: str
    task: str
    enabled: bool = True
    description: Optional[str] = None

class CronSchedule(BaseModel):
    minute: str = "*"
    hour: str = "*"
    day_of_week: str = "*"
    day_of_month: str = "*"
    month_of_year: str = "*"

class ScheduleUpdate(BaseModel):
    enabled: Optional[bool] = None
    cron: Optional[CronSchedule] = None
    args: Optional[List[Any]] = None
    kwargs: Optional[Dict[str, Any]] = None

class ScheduleResponse(ScheduleBase):
    schedule: Dict[str, Any]
    args: List[Any] = []
    kwargs: Dict[str, Any] = {}
    last_run_at: Optional[datetime] = None
    total_run_count: Optional[int] = None

# Define available tasks
AVAILABLE_TASKS = {
    "daily_incremental_update": {
        "task": "tasks.scheduled.daily_incremental_update",
        "description": "Run incremental updates for all active sources",
        "default_schedule": {"hour": 2, "minute": 0}
    },
    "weekly_full_check": {
        "task": "tasks.scheduled.weekly_full_check",
        "description": "Check for stale documents and re-fetch them",
        "default_schedule": {"day_of_week": 0, "hour": 3, "minute": 0}
    },
    "hourly_status_check": {
        "task": "tasks.scheduled.check_running_jobs",
        "description": "Check for stuck jobs and mark them as failed",
        "default_schedule": {"minute": 0}
    }
}

@router.get("/", response_model=List[ScheduleResponse], dependencies=[Depends(get_current_admin)])
async def list_schedules() -> List[ScheduleResponse]:
    """List all scheduled tasks"""
    schedules = []
    
    # Get configured schedules from Celery
    beat_schedule = celery_app.conf.beat_schedule or {}
    
    for name, config in beat_schedule.items():
        schedule_dict = {
            "name": name,
            "task": config.get("task", ""),
            "enabled": config.get("enabled", True),
            "description": None,
            "args": config.get("args", []),
            "kwargs": config.get("kwargs", {})
        }
        
        # Add description from available tasks
        for task_key, task_info in AVAILABLE_TASKS.items():
            if task_info["task"] == config.get("task"):
                schedule_dict["description"] = task_info["description"]
                break
        
        # Convert schedule to dict
        schedule = config.get("schedule")
        if hasattr(schedule, "_fields"):  # crontab
            schedule_dict["schedule"] = {
                "type": "crontab",
                "minute": str(schedule.minute),
                "hour": str(schedule.hour),
                "day_of_week": str(schedule.day_of_week),
                "day_of_month": str(schedule.day_of_month),
                "month_of_year": str(schedule.month_of_year)
            }
        elif hasattr(schedule, "total_seconds"):  # interval
            schedule_dict["schedule"] = {"type": "interval", "seconds": schedule.total_seconds()}
        else:
            # Fallback for unknown schedule types
            schedule_dict["schedule"] = {"type": "unknown", "value": str(schedule)}
        
        # TODO: Get last run info from Celery beat database
        schedule_dict["last_run_at"] = None
        schedule_dict["total_run_count"] = None
        
        schedules.append(ScheduleResponse(**schedule_dict))
    
    return schedules

@router.get("/{schedule_name}", response_model=ScheduleResponse, dependencies=[Depends(get_current_admin)])
async def get_schedule(schedule_name: str) -> ScheduleResponse:
    """Get a specific scheduled task"""
    beat_schedule = celery_app.conf.beat_schedule or {}
    
    if schedule_name not in beat_schedule:
        raise HTTPException(status_code=404, detail="Schedule not found")
    
    config = beat_schedule[schedule_name]
    schedule_dict = {
        "name": schedule_name,
        "task": config.get("task", ""),
        "enabled": config.get("enabled", True),
        "description": None,
        "args": config.get("args", []),
        "kwargs": config.get("kwargs", {})
    }
    
    # Add description
    for task_key, task_info in AVAILABLE_TASKS.items():
        if task_info["task"] == config.get("task"):
            schedule_dict["description"] = task_info["description"]
            break
    
    # Convert schedule
    schedule = config.get("schedule")
    if hasattr(schedule, "_fields"):  # crontab
        schedule_dict["schedule"] = {
            "type": "crontab",
            "minute": str(schedule.minute),
            "hour": str(schedule.hour),
            "day_of_week": str(schedule.day_of_week),
            "day_of_month": str(schedule.day_of_month),
            "month_of_year": str(schedule.month_of_year)
        }
    elif hasattr(schedule, "total_seconds"):  # interval
        schedule_dict["schedule"] = {"type": "interval", "seconds": schedule.total_seconds()}
    else:
        # Fallback for unknown schedule types
        schedule_dict["schedule"] = {"type": "unknown", "value": str(schedule)}
    
    return ScheduleResponse(**schedule_dict)

@router.patch("/{schedule_name}", dependencies=[Depends(get_current_admin)])
async def update_schedule(
    schedule_name: str, 
    update: ScheduleUpdate
) -> Dict[str, str]:
    """Update a scheduled task (requires Celery beat restart)"""
    beat_schedule = celery_app.conf.beat_schedule or {}
    
    if schedule_name not in beat_schedule:
        raise HTTPException(status_code=404, detail="Schedule not found")
    
    # Note: This updates the in-memory config only
    # In production, you'd need to persist this and restart Celery beat
    
    if update.enabled is not None:
        beat_schedule[schedule_name]["enabled"] = update.enabled
    
    if update.cron:
        beat_schedule[schedule_name]["schedule"] = crontab(
            minute=update.cron.minute,
            hour=update.cron.hour,
            day_of_week=update.cron.day_of_week,
            day_of_month=update.cron.day_of_month,
            month_of_year=update.cron.month_of_year
        )
    
    if update.args is not None:
        beat_schedule[schedule_name]["args"] = update.args
    
    if update.kwargs is not None:
        beat_schedule[schedule_name]["kwargs"] = update.kwargs
    
    return {
        "message": "Schedule updated. Note: Celery beat restart required for changes to take effect."
    }

@router.post("/{schedule_name}/run-now", dependencies=[Depends(get_current_admin)])
async def run_schedule_now(
    schedule_name: str,
    background_tasks: BackgroundTasks
) -> Dict[str, Any]:
    """Trigger a scheduled task to run immediately"""
    beat_schedule = celery_app.conf.beat_schedule or {}
    
    if schedule_name not in beat_schedule:
        raise HTTPException(status_code=404, detail="Schedule not found")
    
    task_name = beat_schedule[schedule_name]["task"]
    args = beat_schedule[schedule_name].get("args", [])
    kwargs = beat_schedule[schedule_name].get("kwargs", {})
    
    # Map task names to actual task functions
    task_map = {
        "tasks.scheduled.daily_incremental_update": daily_incremental_update,
        "tasks.scheduled.weekly_full_check": weekly_full_check,
        "tasks.scheduled.check_running_jobs": check_running_jobs,
        "tasks.scheduled.scrape_specific_disease": scrape_specific_disease
    }
    
    task = task_map.get(task_name)
    if not task:
        raise HTTPException(status_code=400, detail=f"Task {task_name} not found")
    
    # Trigger the task
    result = task.delay(*args, **kwargs)
    
    return {
        "task_id": result.id,
        "schedule_name": schedule_name,
        "task": task_name,
        "status": "triggered"
    }

@router.post("/custom/disease-scrape", dependencies=[Depends(get_current_admin)])
async def trigger_disease_scrape(
    disease_term: str,
    sources: Optional[List[str]] = None
) -> Dict[str, Any]:
    """Trigger a custom disease scrape"""
    if sources is None:
        sources = ["clinicaltrials", "pubmed", "reddit"]
    
    result = scrape_specific_disease.delay(disease_term, sources)
    
    return {
        "task_id": result.id,
        "disease_term": disease_term,
        "sources": sources,
        "status": "triggered"
    }

@router.get("/available-tasks/list", dependencies=[Depends(get_current_admin)])
async def list_available_tasks() -> List[Dict[str, Any]]:
    """List all available tasks that can be scheduled"""
    tasks = []
    for key, info in AVAILABLE_TASKS.items():
        tasks.append({
            "key": key,
            "task": info["task"],
            "description": info["description"],
            "default_schedule": info["default_schedule"]
        })
    return tasks