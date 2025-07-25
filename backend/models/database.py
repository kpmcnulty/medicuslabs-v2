from sqlalchemy import (
    Column, Integer, String, Text, Float, Boolean, 
    DateTime, ForeignKey, JSON, Enum, ARRAY
)
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from sqlalchemy.dialects.postgresql import UUID
from pgvector.sqlalchemy import Vector
import enum
from datetime import datetime
from typing import Optional
from core.database import Base

class SourceCategory(str, enum.Enum):
    publications = "publications"
    trials = "trials"
    community = "community"

class DocumentStatus(str, enum.Enum):
    pending = "pending"
    processing = "processing"
    processed = "processed"
    failed = "failed"

class Source(Base):
    __tablename__ = "sources"
    
    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False, unique=True)
    category = Column(Enum(SourceCategory), nullable=False)
    base_url = Column(Text)
    scraper_type = Column(String(100))
    rate_limit = Column(Integer, default=10)
    is_active = Column(Boolean, default=True)
    config = Column(JSON, default={})
    last_crawled = Column(DateTime)
    last_crawled_id = Column(Text)
    crawl_state = Column(JSON, default={})
    association_method = Column(String(20), default='search')
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())
    
    # Relationships
    documents = relationship("Document", back_populates="source")
    crawl_jobs = relationship("CrawlJob", back_populates="source")
    diseases = relationship("Disease", secondary="source_diseases", back_populates="sources")

class Document(Base):
    __tablename__ = "documents"
    
    id = Column(Integer, primary_key=True)
    source_id = Column(Integer, ForeignKey("sources.id", ondelete="CASCADE"))
    external_id = Column(Text)
    url = Column(Text)
    title = Column(Text)
    content = Column(Text)
    summary = Column(Text)
    doc_metadata = Column(JSON, default={})
    status = Column(String(50), default="active")
    language = Column(String(10), default="en")
    relevance_score = Column(Float)
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())
    source_updated_at = Column(DateTime)
    update_count = Column(Integer, default=0)
    embedding = Column(Vector(384))
    
    # Relationships
    source = relationship("Source", back_populates="documents")
    # Note: DocumentDisease relationship disabled due to partitioned table complexity
    
    def get_metadata(self):
        return self.doc_metadata

class Disease(Base):
    __tablename__ = "diseases"
    
    id = Column(Integer, primary_key=True)
    name = Column(String(255), nullable=False, unique=True)
    category = Column(String(100))
    synonyms = Column(ARRAY(Text), default=[])
    search_terms = Column(ARRAY(Text), default=[])
    created_at = Column(DateTime, default=func.now())
    
    # Relationships
    document_diseases = relationship("DocumentDisease", back_populates="disease")
    sources = relationship("Source", secondary="source_diseases", back_populates="diseases")

class SourceDisease(Base):
    __tablename__ = "source_diseases"
    
    source_id = Column(Integer, ForeignKey("sources.id"), primary_key=True)
    disease_id = Column(Integer, ForeignKey("diseases.id"), primary_key=True)
    created_at = Column(DateTime, default=func.now())

class DocumentDisease(Base):
    __tablename__ = "document_diseases"
    
    id = Column(Integer, primary_key=True)
    document_id = Column(Integer, nullable=False)
    disease_id = Column(Integer, ForeignKey("diseases.id", ondelete="CASCADE"))
    relevance_score = Column(Float, default=0.0)
    confidence = Column(Float, default=0.0)
    extracted_terms = Column(ARRAY(Text))
    created_at = Column(DateTime, default=func.now())
    
    # Relationships
    # Note: Document relationship disabled due to partitioned table complexity
    disease = relationship("Disease", back_populates="document_diseases")

class DocumentHistory(Base):
    __tablename__ = "document_history"
    
    id = Column(Integer, primary_key=True)
    document_id = Column(Integer, nullable=False)
    source_id = Column(Integer, ForeignKey("sources.id", ondelete="CASCADE"))
    change_type = Column(String(50), nullable=False)
    old_values = Column(JSON)
    new_values = Column(JSON)
    changed_at = Column(DateTime, default=func.now())

class CrawlJob(Base):
    __tablename__ = "crawl_jobs"
    
    id = Column(Integer, primary_key=True)
    source_id = Column(Integer, ForeignKey("sources.id", ondelete="CASCADE"))
    status = Column(String(50), default="pending")
    started_at = Column(DateTime)
    completed_at = Column(DateTime)
    documents_found = Column(Integer, default=0)
    documents_processed = Column(Integer, default=0)
    errors = Column(Integer, default=0)
    error_details = Column(JSON, default=[])
    config = Column(JSON, default={})
    created_at = Column(DateTime, default=func.now())
    
    # Relationships
    source = relationship("Source", back_populates="crawl_jobs")