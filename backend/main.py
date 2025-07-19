from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api import scrapers, metadata, search_unified, search_by_type
from api.admin import auth as admin_auth
from api.admin import base as admin_base
from api.admin import sources as admin_sources
from api.admin import diseases as admin_diseases
from api.admin import jobs as admin_jobs
from api.admin import schedules as admin_schedules

app = FastAPI(title="Medical Data API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(scrapers.router)
app.include_router(metadata.router)
app.include_router(search_unified.router)
app.include_router(search_by_type.router)

# Include admin routers
app.include_router(admin_auth.router)
app.include_router(admin_base.router)
app.include_router(admin_sources.router)
app.include_router(admin_diseases.router)
app.include_router(admin_jobs.router)
app.include_router(admin_schedules.router)

@app.get("/health")
async def health_check():
    return {"status": "healthy"}

@app.get("/")
async def root():
    return {"message": "Medical Data Aggregation Platform API"}