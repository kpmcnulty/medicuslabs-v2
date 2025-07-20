-- Migration: Simplify date fields by removing scraped_at
-- Date: 2025-01-20

-- Drop the scraped_at column from documents table
ALTER TABLE documents DROP COLUMN IF EXISTS scraped_at;

-- Add comment to clarify the meaning of remaining date fields
COMMENT ON COLUMN documents.created_at IS 'Timestamp when the document was first ingested into our system';
COMMENT ON COLUMN documents.source_updated_at IS 'Timestamp when the source indicates the document was last updated';
COMMENT ON COLUMN documents.updated_at IS 'Timestamp when our database record was last modified';