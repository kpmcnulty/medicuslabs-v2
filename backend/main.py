from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api import scrapers, metadata, search

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
app.include_router(search.router)

@app.get("/health")
async def health_check():
    return {"status": "healthy"}

@app.get("/")
async def root():
    return {"message": "Medical Data Aggregation Platform API"}