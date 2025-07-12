-- Migration to fix schema issues and add configuration support
-- This migration:
-- 1. Fixes crawl_jobs table to match SQLAlchemy models
-- 2. Adds configuration and state tracking to sources table

-- Fix crawl_jobs table
ALTER TABLE crawl_jobs 
    ADD COLUMN IF NOT EXISTS config JSONB DEFAULT '{}',
    ADD COLUMN IF NOT EXISTS documents_processed INTEGER DEFAULT 0,
    ADD COLUMN IF NOT EXISTS errors INTEGER DEFAULT 0,
    ADD COLUMN IF NOT EXISTS error_details JSONB DEFAULT '[]';

-- Rename documents_updated to documents_processed if it exists
DO $$ 
BEGIN
    IF EXISTS (SELECT 1 FROM information_schema.columns 
               WHERE table_name = 'crawl_jobs' 
               AND column_name = 'documents_updated') THEN
        ALTER TABLE crawl_jobs RENAME COLUMN documents_updated TO documents_processed;
    END IF;
END $$;

-- Add configuration and state tracking to sources table
ALTER TABLE sources 
    ADD COLUMN IF NOT EXISTS default_config JSONB DEFAULT '{}',
    ADD COLUMN IF NOT EXISTS last_crawled TIMESTAMP,
    ADD COLUMN IF NOT EXISTS last_crawled_id TEXT,
    ADD COLUMN IF NOT EXISTS crawl_state JSONB DEFAULT '{}';

-- Add comments explaining the new columns
COMMENT ON COLUMN sources.default_config IS 'Default configuration for this source (limits, windows, filters, etc.)';
COMMENT ON COLUMN sources.last_crawled IS 'Timestamp of last successful crawl for incremental updates';
COMMENT ON COLUMN sources.last_crawled_id IS 'ID of last processed document for pagination';
COMMENT ON COLUMN sources.crawl_state IS 'Persistent state for crawling (pagination tokens, offsets, etc.)';

COMMENT ON COLUMN crawl_jobs.config IS 'Job-specific configuration overrides';
COMMENT ON COLUMN crawl_jobs.documents_processed IS 'Number of documents successfully processed';
COMMENT ON COLUMN crawl_jobs.errors IS 'Number of errors encountered';
COMMENT ON COLUMN crawl_jobs.error_details IS 'Detailed error information for debugging';

-- Set default configurations for existing sources
UPDATE sources SET default_config = 
    CASE 
        WHEN name = 'ClinicalTrials.gov' THEN 
            '{"initial_limit": 1000, "incremental_limit": 100, "update_window_hours": 48, "pagination_size": 100}'::jsonb
        WHEN name = 'PubMed' THEN 
            '{"initial_limit": 500, "incremental_limit": 50, "update_window_hours": 24, "pagination_size": 20}'::jsonb
        WHEN name = 'Reddit Medical' THEN 
            '{"initial_limit": 200, "incremental_limit": 25, "update_window_hours": 12, "post_types": ["new", "hot"], "include_comments": true}'::jsonb
        ELSE 
            '{"initial_limit": 100, "incremental_limit": 20, "update_window_hours": 24}'::jsonb
    END
WHERE default_config = '{}';