-- Add missing columns to documents table
ALTER TABLE documents 
    ADD COLUMN IF NOT EXISTS update_count INTEGER DEFAULT 0,
    ADD COLUMN IF NOT EXISTS last_checked_at TIMESTAMP;

-- Add comments
COMMENT ON COLUMN documents.update_count IS 'Number of times this document has been updated';
COMMENT ON COLUMN documents.last_checked_at IS 'Last time we checked this document for updates';