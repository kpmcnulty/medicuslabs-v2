from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime
from enum import Enum

class SourceType(str, Enum):
    primary = "primary"
    secondary = "secondary"

class AssociationMethod(str, Enum):
    linked = "linked"
    search = "search"

class DocumentStatus(str, Enum):
    pending = "pending"
    processing = "processing"
    processed = "processed"
    failed = "failed"

# Source schemas
class SourceBase(BaseModel):
    name: str
    type: SourceType
    base_url: Optional[str] = None
    config: Dict[str, Any] = {}
    is_active: bool = True
    association_method: AssociationMethod = AssociationMethod.search

class SourceCreate(SourceBase):
    pass

class SourceUpdate(BaseModel):
    config: Optional[Dict[str, Any]] = None
    is_active: Optional[bool] = None

class SourceResponse(SourceBase):
    id: int
    last_crawled: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime
    diseases: List['DiseaseResponse'] = []
    
    class Config:
        from_attributes = True

# Document schemas
class DocumentBase(BaseModel):
    source_id: int
    external_id: str
    url: Optional[str] = None
    title: str
    content: str
    summary: Optional[str] = None
    metadata: Dict[str, Any] = {}

class DocumentCreate(DocumentBase):
    pass

class DocumentUpdate(BaseModel):
    status: Optional[DocumentStatus] = None
    embedding: Optional[List[float]] = None
    relevance_score: Optional[float] = None

class DocumentResponse(DocumentBase):
    id: int
    status: DocumentStatus
    language: str
    relevance_score: Optional[float] = None
    created_at: datetime
    updated_at: datetime
    source_updated_at: Optional[datetime] = None
    
    class Config:
        from_attributes = True

# Disease schemas
class DiseaseBase(BaseModel):
    name: str
    category: Optional[str] = None
    synonyms: List[str] = []
    search_terms: List[str] = []

class DiseaseCreate(DiseaseBase):
    pass

class DiseaseResponse(DiseaseBase):
    id: int
    created_at: datetime
    
    class Config:
        from_attributes = True

# Crawl job schemas
class CrawlJobCreate(BaseModel):
    source_id: int
    config: Dict[str, Any] = {}

class CrawlJobUpdate(BaseModel):
    status: Optional[str] = None
    documents_found: Optional[int] = None
    documents_processed: Optional[int] = None
    errors: Optional[int] = None
    error_details: Optional[List[Dict[str, Any]]] = None

class CrawlJobResponse(BaseModel):
    id: int
    source_id: int
    status: str
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    documents_found: int
    documents_processed: int
    errors: int
    error_details: List[Dict[str, Any]]
    config: Dict[str, Any]
    created_at: datetime
    
    class Config:
        from_attributes = True

# Scraping request schemas
class ScrapeRequest(BaseModel):
    source_name: str
    disease_ids: List[int]
    options: Dict[str, Any] = {}

class ScrapeResponse(BaseModel):
    job_id: int
    message: str
    status: str
    details: Dict[str, Any] = {}

# Search schemas
class SearchResult(BaseModel):
    id: int
    title: str
    snippet: str
    url: Optional[str] = None
    source: str
    source_type: str
    created_at: datetime
    relevance_score: float
    disease_tags: List[str] = []
    
class SearchResponse(BaseModel):
    results: List[SearchResult]
    total: int
    limit: int
    offset: int
    query: str
    search_type: str
    execution_time_ms: Optional[int] = None
    
class DocumentDetail(BaseModel):
    id: int
    source: str
    source_type: str
    external_id: str
    url: Optional[str] = None
    title: str
    content: str
    summary: Optional[str] = None
    metadata: Dict[str, Any] = {}
    diseases: List[str] = []
    relevance_score: Optional[float] = None
    created_at: datetime
    updated_at: datetime
    source_updated_at: Optional[datetime] = None
    
    class Config:
        from_attributes = True