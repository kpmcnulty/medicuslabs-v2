-- Migration: cleanup_unused_tables
-- Created: 2025-07-11
-- Remove unused tables to simplify schema

-- Drop document_history table if it exists
DROP TABLE IF EXISTS document_history CASCADE;

-- Remove any references in comments
COMMENT ON TABLE documents IS 'Central storage for all medical documents from various sources';