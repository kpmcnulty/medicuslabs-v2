-- Remaining performance optimization indexes

-- Already created: idx_documents_source_created_desc

CREATE INDEX CONCURRENTLY idx_documents_source_updated_desc 
ON documents(source_id, updated_at DESC);

CREATE INDEX CONCURRENTLY idx_documents_source_source_updated_desc 
ON documents(source_id, source_updated_at DESC);

-- JSONB expression indexes for frequently queried metadata fields
CREATE INDEX CONCURRENTLY idx_documents_metadata_phase 
ON documents((doc_metadata->>'phase')) 
WHERE doc_metadata->>'phase' IS NOT NULL;

CREATE INDEX CONCURRENTLY idx_documents_metadata_status 
ON documents((doc_metadata->>'status'))
WHERE doc_metadata->>'status' IS NOT NULL;

CREATE INDEX CONCURRENTLY idx_documents_metadata_authors_gin 
ON documents USING gin((doc_metadata->'authors'))
WHERE doc_metadata->'authors' IS NOT NULL;

CREATE INDEX CONCURRENTLY idx_documents_metadata_report_type 
ON documents((doc_metadata->>'report_type'))
WHERE doc_metadata->>'report_type' IS NOT NULL;

-- Recent documents (last 90 days)
CREATE INDEX CONCURRENTLY idx_documents_recent 
ON documents(created_at DESC, source_id)
WHERE created_at > CURRENT_DATE - INTERVAL '90 days';

-- Combined text search with source
CREATE INDEX CONCURRENTLY idx_documents_title_trgm_source 
ON documents USING gin(title gin_trgm_ops, source_id);

-- Covering index for list queries
CREATE INDEX CONCURRENTLY idx_documents_covering_list 
ON documents(source_id, created_at DESC) 
INCLUDE (title, url, doc_metadata);

-- Disease table optimizations
CREATE INDEX CONCURRENTLY idx_diseases_name_lower 
ON diseases(lower(name));

CREATE INDEX CONCURRENTLY idx_diseases_aliases_gin 
ON diseases USING gin(aliases)
WHERE aliases IS NOT NULL;

-- Sources table optimizations
CREATE INDEX CONCURRENTLY idx_sources_active 
ON sources(is_active, priority DESC);

-- Function-based date index
CREATE INDEX CONCURRENTLY idx_documents_date_func 
ON documents(DATE(created_at), source_id);

-- Document-disease relationship
CREATE INDEX CONCURRENTLY idx_document_diseases_disease_doc 
ON document_diseases(disease_id, document_id);

-- External ID lookups
CREATE INDEX CONCURRENTLY idx_documents_external_id 
ON documents(external_id);

-- Metadata date fields
CREATE INDEX CONCURRENTLY idx_documents_metadata_posted_date_ts
ON documents(((doc_metadata->>'posted_date')::timestamp))
WHERE doc_metadata->>'posted_date' IS NOT NULL;

CREATE INDEX CONCURRENTLY idx_documents_metadata_created_date_ts
ON documents(((doc_metadata->>'created_date')::timestamp))
WHERE doc_metadata->>'created_date' IS NOT NULL;

-- Update statistics
ANALYZE documents;
ANALYZE sources;
ANALYZE diseases;
ANALYZE document_diseases;