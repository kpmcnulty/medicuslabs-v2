-- Medical Data Platform - Complete Schema
-- This is the single source of truth for the database schema

-- Enable required extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pgcrypto";
CREATE EXTENSION IF NOT EXISTS "pg_trgm";
CREATE EXTENSION IF NOT EXISTS "btree_gin";
CREATE EXTENSION IF NOT EXISTS "vector";

-- Sources table - defines where we get medical data
CREATE TABLE IF NOT EXISTS sources (
    id SERIAL PRIMARY KEY,
    name VARCHAR(255) NOT NULL UNIQUE,
    category VARCHAR(50) NOT NULL CHECK (category IN ('publications', 'trials', 'community')),
    base_url TEXT,
    scraper_type VARCHAR(100), -- pubmed_api, clinicaltrials_api, web_scraper, etc.
    rate_limit INTEGER DEFAULT 10,
    is_active BOOLEAN DEFAULT true,
    config JSONB DEFAULT '{}', -- API keys, special settings, etc.
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Documents table - stores all medical documents with flexible metadata
CREATE TABLE IF NOT EXISTS documents (
    id SERIAL PRIMARY KEY,
    source_id INTEGER REFERENCES sources(id) ON DELETE CASCADE,
    external_id TEXT NOT NULL, -- ID from the source (PMID, NCT ID, post ID, etc.)
    url TEXT,
    title TEXT,
    content TEXT,
    summary TEXT,
    doc_metadata JSONB DEFAULT '{}', -- ALL source-specific data goes here
    language VARCHAR(10) DEFAULT 'en',
    status VARCHAR(50) DEFAULT 'active',
    relevance_score FLOAT,
    embedding vector(384), -- For future semantic search
    
    -- Timestamps
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    scraped_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    source_updated_at TIMESTAMP, -- When the source last updated this document
    
    -- Prevent duplicate documents from same source
    CONSTRAINT uk_documents_source_external_id UNIQUE (source_id, external_id)
);

-- Diseases table - standardized disease/condition names
CREATE TABLE IF NOT EXISTS diseases (
    id SERIAL PRIMARY KEY,
    name VARCHAR(255) NOT NULL UNIQUE,
    category VARCHAR(100), -- neurological, cardiovascular, etc.
    synonyms TEXT[], -- Alternative names
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Junction table for document-disease relationships
CREATE TABLE IF NOT EXISTS document_diseases (
    document_id INTEGER REFERENCES documents(id) ON DELETE CASCADE,
    disease_id INTEGER REFERENCES diseases(id) ON DELETE CASCADE,
    relevance_score FLOAT DEFAULT 1.0,
    PRIMARY KEY (document_id, disease_id)
);

-- Crawl jobs table for tracking scraper runs
CREATE TABLE IF NOT EXISTS crawl_jobs (
    id SERIAL PRIMARY KEY,
    source_id INTEGER REFERENCES sources(id),
    status VARCHAR(50) DEFAULT 'pending',
    started_at TIMESTAMP,
    completed_at TIMESTAMP,
    documents_found INTEGER DEFAULT 0,
    documents_updated INTEGER DEFAULT 0,
    error_message TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Create indexes for performance

-- Full-text search indexes
CREATE INDEX idx_documents_title_trgm ON documents USING gin (title gin_trgm_ops);
CREATE INDEX idx_documents_content_trgm ON documents USING gin (content gin_trgm_ops);
CREATE INDEX idx_documents_fulltext ON documents USING gin (
    to_tsvector('english', COALESCE(title, '') || ' ' || COALESCE(content, '') || ' ' || COALESCE(summary, ''))
);

-- JSONB indexes for metadata queries
CREATE INDEX idx_documents_metadata_gin ON documents USING gin (doc_metadata);

-- Note: Partial indexes by category would be nice but PostgreSQL doesn't allow subqueries in WHERE clause
-- Instead, we'll rely on the general GIN index and the source_id index for performance

-- Standard indexes
CREATE INDEX idx_documents_source_id ON documents (source_id);
CREATE INDEX idx_documents_scraped_at ON documents (scraped_at DESC);
CREATE INDEX idx_documents_source_updated ON documents (source_id, source_updated_at DESC);
CREATE INDEX idx_document_diseases_document_id ON document_diseases (document_id);
CREATE INDEX idx_document_diseases_disease_id ON document_diseases (disease_id);
CREATE INDEX idx_sources_category ON sources (category);
CREATE INDEX idx_sources_active ON sources (is_active) WHERE is_active = true;

-- Add comments explaining design decisions
COMMENT ON TABLE sources IS 'Data sources for medical information - APIs, websites, forums, etc.';
COMMENT ON COLUMN sources.category IS 'Type of medical content: publications (research), trials (clinical trials), community (patient forums)';
COMMENT ON COLUMN sources.config IS 'Source-specific configuration like API keys, custom headers, etc.';

COMMENT ON TABLE documents IS 'All medical documents stored with flexible JSONB metadata';
COMMENT ON COLUMN documents.doc_metadata IS 'All source-specific fields stored as JSONB for maximum flexibility';
COMMENT ON COLUMN documents.external_id IS 'The ID used by the source (PMID for PubMed, NCT ID for trials, post ID for forums)';

COMMENT ON TABLE diseases IS 'Standardized disease and condition names for consistent searching';
COMMENT ON TABLE document_diseases IS 'Many-to-many relationship between documents and diseases they mention';