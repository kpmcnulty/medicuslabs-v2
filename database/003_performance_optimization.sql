-- Migration 003: Performance Optimization Indexes
-- Sprint 0: Core Infrastructure - Database Optimization
-- This migration adds critical indexes identified in the optimization analysis

-- Enable query performance monitoring
CREATE EXTENSION IF NOT EXISTS pg_stat_statements;

-- 1. Composite indexes for common query patterns
-- Main document search pattern: source + type + dates + metadata
CREATE INDEX CONCURRENTLY idx_documents_source_type_external_created 
ON documents(source_id, document_type, external_created_date DESC);

CREATE INDEX CONCURRENTLY idx_documents_source_type_updated 
ON documents(source_id, document_type, updated_at DESC);

-- Disease-based queries optimization
CREATE INDEX CONCURRENTLY idx_documents_disease_source_created 
ON documents(disease_id, source_id, external_created_date DESC);

-- 2. JSONB expression indexes for frequently queried metadata fields
-- Clinical trials phase filtering
CREATE INDEX CONCURRENTLY idx_documents_metadata_phase 
ON documents((metadata->>'phase')) 
WHERE document_type = 'clinical_trial';

-- Clinical trials status filtering
CREATE INDEX CONCURRENTLY idx_documents_metadata_status 
ON documents((metadata->>'status')) 
WHERE document_type = 'clinical_trial';

-- Authors search (for research papers)
CREATE INDEX CONCURRENTLY idx_documents_metadata_authors_gin 
ON documents USING gin((metadata->'authors'));

-- FAERS report type filtering
CREATE INDEX CONCURRENTLY idx_documents_metadata_report_type 
ON documents((metadata->>'report_type')) 
WHERE document_type = 'fda_adverse_event';

-- 3. Partial indexes for filtered queries
-- Active documents only (non-deleted)
CREATE INDEX CONCURRENTLY idx_documents_active 
ON documents(source_id, document_type, external_created_date DESC) 
WHERE deleted_at IS NULL;

-- Recent documents (last 90 days) - frequently accessed
CREATE INDEX CONCURRENTLY idx_documents_recent 
ON documents(external_created_date DESC, source_id, document_type) 
WHERE external_created_date > CURRENT_DATE - INTERVAL '90 days' 
AND deleted_at IS NULL;

-- 4. Optimized text search indexes
-- Combined text search with source filtering
CREATE INDEX CONCURRENTLY idx_documents_title_trgm_source 
ON documents USING gin(title gin_trgm_ops, source_id);

-- 5. Covering indexes for common projections
-- Document list queries that don't need full content
CREATE INDEX CONCURRENTLY idx_documents_covering_list 
ON documents(source_id, document_type, external_created_date DESC) 
INCLUDE (title, url, metadata);

-- 6. Disease table optimizations
CREATE INDEX CONCURRENTLY idx_diseases_name_lower 
ON diseases(lower(name));

CREATE INDEX CONCURRENTLY idx_diseases_aliases_gin 
ON diseases USING gin(aliases);

-- 7. Sources table optimizations
CREATE INDEX CONCURRENTLY idx_sources_active 
ON sources(is_active, priority DESC);

-- 8. Function-based index for complex date queries
-- Handles the DATE() casting in queries
CREATE INDEX CONCURRENTLY idx_documents_date_func 
ON documents(DATE(external_created_date), source_id) 
WHERE deleted_at IS NULL;

-- 9. Analyze tables to update statistics
ANALYZE documents;
ANALYZE sources;
ANALYZE diseases;

-- Add comments to document the indexes
COMMENT ON INDEX idx_documents_source_type_external_created IS 'Primary query pattern: filter by source and type, sort by date';
COMMENT ON INDEX idx_documents_metadata_phase IS 'Clinical trials phase filtering';
COMMENT ON INDEX idx_documents_recent IS 'Optimized for recent documents queries (90 days)';
COMMENT ON INDEX idx_documents_covering_list IS 'Covering index for list queries without content fetch';