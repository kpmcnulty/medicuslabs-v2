-- Medical Data Platform - Complete Schema
-- This is the SINGLE source of truth for the database schema
-- All migrations have been consolidated into this file

-- Enable required extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pgcrypto";
CREATE EXTENSION IF NOT EXISTS "pg_trgm";
CREATE EXTENSION IF NOT EXISTS "btree_gin";
CREATE EXTENSION IF NOT EXISTS "vector";

-- Drop tables if they exist to ensure clean state
DROP TABLE IF EXISTS document_diseases CASCADE;
DROP TABLE IF EXISTS documents CASCADE;
DROP TABLE IF EXISTS crawl_jobs CASCADE;
DROP TABLE IF EXISTS source_diseases CASCADE;
DROP TABLE IF EXISTS sources CASCADE;
DROP TABLE IF EXISTS diseases CASCADE;
DROP TABLE IF EXISTS admin_users CASCADE;

-- Admin users table for authentication
CREATE TABLE admin_users (
    id SERIAL PRIMARY KEY,
    username VARCHAR(255) NOT NULL UNIQUE,
    password_hash VARCHAR(255) NOT NULL,
    is_active BOOLEAN DEFAULT true,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Diseases table - standardized disease/condition names
CREATE TABLE diseases (
    id SERIAL PRIMARY KEY,
    name VARCHAR(255) NOT NULL UNIQUE,
    category VARCHAR(100), -- neurological, cardiovascular, etc.
    synonyms TEXT[] DEFAULT ARRAY[]::TEXT[], -- Alternative names
    search_terms TEXT[] DEFAULT ARRAY[]::TEXT[], -- Terms used for searching
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Sources table - defines where we get medical data
CREATE TABLE sources (
    id SERIAL PRIMARY KEY,
    name VARCHAR(255) NOT NULL UNIQUE,
    category VARCHAR(50) NOT NULL CHECK (category IN ('publications', 'trials', 'community', 'safety')),
    base_url TEXT,
    scraper_type VARCHAR(100), -- pubmed_api, clinicaltrials_api, reddit_scraper, etc.
    rate_limit INTEGER DEFAULT 10,
    is_active BOOLEAN DEFAULT true,
    config JSONB DEFAULT '{}', -- Scraper-specific settings
    association_method VARCHAR(20) DEFAULT 'search' CHECK (association_method IN ('linked', 'search')),
    
    -- Crawl state tracking
    last_crawled TIMESTAMP,
    last_crawled_id TEXT,
    crawl_state JSONB DEFAULT '{}',
    
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Junction table for linking sources to specific diseases (for association_method = 'linked')
CREATE TABLE source_diseases (
    source_id INTEGER REFERENCES sources(id) ON DELETE CASCADE,
    disease_id INTEGER REFERENCES diseases(id) ON DELETE CASCADE,
    PRIMARY KEY (source_id, disease_id)
);

-- Documents table - stores all medical documents with flexible metadata
CREATE TABLE documents (
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
    
    -- Version tracking
    update_count INTEGER DEFAULT 0,
    last_checked_at TIMESTAMP,
    
    -- Timestamps
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    scraped_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    source_updated_at TIMESTAMP, -- When the source last updated this document
    
    -- Prevent duplicate documents from same source
    CONSTRAINT uk_documents_source_external_id UNIQUE (source_id, external_id)
);

-- Junction table for document-disease relationships
CREATE TABLE document_diseases (
    document_id INTEGER REFERENCES documents(id) ON DELETE CASCADE,
    disease_id INTEGER REFERENCES diseases(id) ON DELETE CASCADE,
    relevance_score FLOAT DEFAULT 1.0,
    PRIMARY KEY (document_id, disease_id)
);

-- Crawl jobs table for tracking scraper runs
CREATE TABLE crawl_jobs (
    id SERIAL PRIMARY KEY,
    source_id INTEGER REFERENCES sources(id),
    status VARCHAR(50) DEFAULT 'pending' CHECK (status IN ('pending', 'running', 'completed', 'failed', 'cancelled')),
    started_at TIMESTAMP,
    completed_at TIMESTAMP,
    
    -- Job metrics
    documents_found INTEGER DEFAULT 0,
    documents_processed INTEGER DEFAULT 0,
    documents_created INTEGER DEFAULT 0,
    documents_updated INTEGER DEFAULT 0,
    documents_unchanged INTEGER DEFAULT 0,
    documents_failed INTEGER DEFAULT 0,
    errors INTEGER DEFAULT 0,
    
    -- Error tracking
    error_message TEXT,
    error_details JSONB DEFAULT '[]',
    retry_count INTEGER DEFAULT 0,
    http_errors JSONB DEFAULT '{}',
    
    -- Performance metrics
    performance_metrics JSONB DEFAULT '{}',
    
    -- Job configuration
    config JSONB DEFAULT '{}',
    
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
CREATE INDEX idx_sources_config_gin ON sources USING gin (config);
CREATE INDEX idx_crawl_jobs_config_gin ON crawl_jobs USING gin (config);

-- Standard indexes
CREATE INDEX idx_documents_source_id ON documents (source_id);
CREATE INDEX idx_documents_scraped_at ON documents (scraped_at DESC);
CREATE INDEX idx_documents_source_updated ON documents (source_id, source_updated_at DESC);
CREATE INDEX idx_document_diseases_document_id ON document_diseases (document_id);
CREATE INDEX idx_document_diseases_disease_id ON document_diseases (disease_id);
CREATE INDEX idx_sources_disease_id ON source_diseases (disease_id);
CREATE INDEX idx_crawl_jobs_source_id ON crawl_jobs (source_id);
CREATE INDEX idx_crawl_jobs_status ON crawl_jobs (status);

-- Comments for clarity
COMMENT ON TABLE sources IS 'Defines data sources - both APIs (PubMed, ClinicalTrials) and specific communities (subreddits)';
COMMENT ON COLUMN sources.association_method IS 'How documents are linked to diseases: "search" = by search terms, "linked" = pre-linked to specific diseases';
COMMENT ON COLUMN sources.config IS 'Source-specific configuration: API keys, subreddit names, etc.';

COMMENT ON TABLE source_diseases IS 'Links sources to specific diseases (only used when association_method = "linked")';

COMMENT ON TABLE diseases IS 'Standardized disease/condition list with search terms';
COMMENT ON COLUMN diseases.search_terms IS 'Search terms used by "search" type sources to find relevant documents';

COMMENT ON TABLE documents IS 'Core document storage with flexible JSONB metadata for each source type';
COMMENT ON COLUMN documents.doc_metadata IS 'All source-specific fields: authors, pmid, phase, status, journal, etc.';

-- Comments for crawl_jobs columns
COMMENT ON COLUMN crawl_jobs.documents_updated IS 'Number of existing documents that were updated with new data';
COMMENT ON COLUMN crawl_jobs.documents_created IS 'Number of new documents created during this job';
COMMENT ON COLUMN crawl_jobs.documents_unchanged IS 'Number of documents checked but not updated (already up-to-date)';
COMMENT ON COLUMN crawl_jobs.documents_failed IS 'Number of documents that failed to process';
COMMENT ON COLUMN crawl_jobs.http_errors IS 'HTTP error counts by status code (e.g., {"403": 5, "429": 3})';
COMMENT ON COLUMN crawl_jobs.performance_metrics IS 'Performance data: request_count, total_duration, avg_response_time, etc.';
COMMENT ON COLUMN crawl_jobs.retry_count IS 'Total number of retry attempts made during this job';

-- Function to update updated_at timestamp
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ language 'plpgsql';

-- Create triggers for updated_at
CREATE TRIGGER update_sources_updated_at BEFORE UPDATE ON sources
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_documents_updated_at BEFORE UPDATE ON documents
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();