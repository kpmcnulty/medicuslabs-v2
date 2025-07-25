-- Migration 003: Performance Optimization Indexes (Fixed for actual schema)
-- Sprint 0: Core Infrastructure - Database Optimization
-- This migration adds critical indexes identified in the optimization analysis

-- Enable query performance monitoring
CREATE EXTENSION IF NOT EXISTS pg_stat_statements;

-- 1. Composite indexes for common query patterns
-- Main document search pattern: source + dates + metadata
CREATE INDEX CONCURRENTLY idx_documents_source_created_desc 
ON documents(source_id, created_at DESC);

CREATE INDEX CONCURRENTLY idx_documents_source_updated_desc 
ON documents(source_id, updated_at DESC);

CREATE INDEX CONCURRENTLY idx_documents_source_source_updated_desc 
ON documents(source_id, source_updated_at DESC);

-- 2. JSONB expression indexes for frequently queried metadata fields
-- Clinical trials phase filtering
CREATE INDEX CONCURRENTLY idx_documents_metadata_phase 
ON documents((doc_metadata->>'phase')) 
WHERE doc_metadata->>'phase' IS NOT NULL;

-- Clinical trials status filtering  
CREATE INDEX CONCURRENTLY idx_documents_metadata_status 
ON documents((doc_metadata->>'status'))
WHERE doc_metadata->>'status' IS NOT NULL;

-- Authors search (for research papers)
CREATE INDEX CONCURRENTLY idx_documents_metadata_authors_gin 
ON documents USING gin((doc_metadata->'authors'))
WHERE doc_metadata->'authors' IS NOT NULL;

-- FAERS report type filtering
CREATE INDEX CONCURRENTLY idx_documents_metadata_report_type 
ON documents((doc_metadata->>'report_type'))
WHERE doc_metadata->>'report_type' IS NOT NULL;

-- 3. Partial indexes for filtered queries
-- Recent documents (last 90 days) - frequently accessed
CREATE INDEX CONCURRENTLY idx_documents_recent 
ON documents(created_at DESC, source_id)
WHERE created_at > CURRENT_DATE - INTERVAL '90 days';

-- 4. Optimized text search indexes
-- Combined text search with source filtering
CREATE INDEX CONCURRENTLY idx_documents_title_trgm_source 
ON documents USING gin(title gin_trgm_ops, source_id);

-- 5. Covering indexes for common projections
-- Document list queries that don't need full content
CREATE INDEX CONCURRENTLY idx_documents_covering_list 
ON documents(source_id, created_at DESC) 
INCLUDE (title, url, doc_metadata);

-- 6. Disease table optimizations
CREATE INDEX CONCURRENTLY idx_diseases_name_lower 
ON diseases(lower(name));

CREATE INDEX CONCURRENTLY idx_diseases_aliases_gin 
ON diseases USING gin(aliases)
WHERE aliases IS NOT NULL;

-- 7. Sources table optimizations
CREATE INDEX CONCURRENTLY idx_sources_active 
ON sources(is_active, priority DESC);

-- 8. Function-based index for complex date queries
-- Handles the DATE() casting in queries
CREATE INDEX CONCURRENTLY idx_documents_date_func 
ON documents(DATE(created_at), source_id);

-- 9. Document-disease relationship optimization
CREATE INDEX CONCURRENTLY idx_document_diseases_disease_doc 
ON document_diseases(disease_id, document_id);

-- 10. Composite index for disease filtering with source
CREATE INDEX CONCURRENTLY idx_documents_disease_join 
ON documents(id, source_id) 
WHERE id IN (SELECT document_id FROM document_diseases);

-- 11. Add index for external_id lookups (important for deduplication)
CREATE INDEX CONCURRENTLY idx_documents_external_id 
ON documents(external_id);

-- 12. Metadata date fields used in sorting
CREATE INDEX CONCURRENTLY idx_documents_metadata_posted_date_ts
ON documents(((doc_metadata->>'posted_date')::timestamp))
WHERE doc_metadata->>'posted_date' IS NOT NULL;

CREATE INDEX CONCURRENTLY idx_documents_metadata_created_date_ts
ON documents(((doc_metadata->>'created_date')::timestamp))
WHERE doc_metadata->>'created_date' IS NOT NULL;

-- 13. Analyze tables to update statistics
ANALYZE documents;
ANALYZE sources;
ANALYZE diseases;
ANALYZE document_diseases;

-- Add comments to document the indexes
COMMENT ON INDEX idx_documents_source_created_desc IS 'Primary query pattern: filter by source, sort by date';
COMMENT ON INDEX idx_documents_metadata_phase IS 'Clinical trials phase filtering';
COMMENT ON INDEX idx_documents_recent IS 'Optimized for recent documents queries (90 days)';
COMMENT ON INDEX idx_documents_covering_list IS 'Covering index for list queries without content fetch';