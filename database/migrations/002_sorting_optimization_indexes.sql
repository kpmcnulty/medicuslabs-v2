-- Migration: Add sorting optimization indexes
-- Purpose: Improve performance for common sorting operations in the unified search API
-- Date: 2025-07-21

-- Check if indexes already exist before creating
DO $$
BEGIN
    -- Basic sorting indexes
    IF NOT EXISTS (SELECT 1 FROM pg_indexes WHERE indexname = 'idx_documents_created_at') THEN
        CREATE INDEX idx_documents_created_at ON documents (created_at DESC);
        RAISE NOTICE 'Created index: idx_documents_created_at';
    END IF;

    IF NOT EXISTS (SELECT 1 FROM pg_indexes WHERE indexname = 'idx_documents_updated_at') THEN
        CREATE INDEX idx_documents_updated_at ON documents (updated_at DESC);
        RAISE NOTICE 'Created index: idx_documents_updated_at';
    END IF;

    IF NOT EXISTS (SELECT 1 FROM pg_indexes WHERE indexname = 'idx_documents_title') THEN
        CREATE INDEX idx_documents_title ON documents (title);
        RAISE NOTICE 'Created index: idx_documents_title';
    END IF;

    IF NOT EXISTS (SELECT 1 FROM pg_indexes WHERE indexname = 'idx_documents_source_created') THEN
        CREATE INDEX idx_documents_source_created ON documents (source_id, created_at DESC);
        RAISE NOTICE 'Created index: idx_documents_source_created';
    END IF;

    -- Composite index for common query patterns (covering index)
    IF NOT EXISTS (SELECT 1 FROM pg_indexes WHERE indexname = 'idx_documents_source_category_created') THEN
        CREATE INDEX idx_documents_source_category_created ON documents (source_id, created_at DESC) 
          INCLUDE (title, url, summary);
        RAISE NOTICE 'Created index: idx_documents_source_category_created';
    END IF;

    -- JSONB expression indexes for metadata sorting
    IF NOT EXISTS (SELECT 1 FROM pg_indexes WHERE indexname = 'idx_documents_posted_date') THEN
        CREATE INDEX idx_documents_posted_date ON documents ((doc_metadata->>'posted_date')) 
          WHERE doc_metadata->>'posted_date' IS NOT NULL;
        RAISE NOTICE 'Created index: idx_documents_posted_date';
    END IF;

    IF NOT EXISTS (SELECT 1 FROM pg_indexes WHERE indexname = 'idx_documents_publication_date') THEN
        CREATE INDEX idx_documents_publication_date ON documents ((doc_metadata->>'publication_date')) 
          WHERE doc_metadata->>'publication_date' IS NOT NULL;
        RAISE NOTICE 'Created index: idx_documents_publication_date';
    END IF;

    IF NOT EXISTS (SELECT 1 FROM pg_indexes WHERE indexname = 'idx_documents_start_date') THEN
        CREATE INDEX idx_documents_start_date ON documents ((doc_metadata->>'start_date')) 
          WHERE doc_metadata->>'start_date' IS NOT NULL;
        RAISE NOTICE 'Created index: idx_documents_start_date';
    END IF;

    -- Analyze tables to update statistics after index creation
    ANALYZE documents;
    ANALYZE sources;
    
    RAISE NOTICE 'Sorting optimization indexes migration completed';
END $$;