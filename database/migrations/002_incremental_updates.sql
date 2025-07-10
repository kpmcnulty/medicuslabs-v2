-- Add columns for incremental update tracking

-- Add last_crawled_id to sources table to track last document processed
ALTER TABLE sources 
ADD COLUMN IF NOT EXISTS last_crawled_id TEXT,
ADD COLUMN IF NOT EXISTS crawl_state JSONB DEFAULT '{}';

-- Add columns to documents table for update tracking
ALTER TABLE documents 
ADD COLUMN IF NOT EXISTS last_checked_at TIMESTAMP,
ADD COLUMN IF NOT EXISTS source_updated_at TIMESTAMP,
ADD COLUMN IF NOT EXISTS update_count INTEGER DEFAULT 0;

-- Create index for efficient incremental queries
CREATE INDEX IF NOT EXISTS idx_documents_source_updated_at ON documents(source_id, source_updated_at DESC);
CREATE INDEX IF NOT EXISTS idx_documents_last_checked_at ON documents(last_checked_at);

-- Add document history table to track changes
CREATE TABLE IF NOT EXISTS document_history (
    id SERIAL PRIMARY KEY,
    document_id INTEGER NOT NULL,
    source_id INTEGER NOT NULL,
    change_type VARCHAR(50) NOT NULL, -- 'created', 'updated', 'status_changed', etc.
    old_values JSONB,
    new_values JSONB,
    changed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (source_id) REFERENCES sources(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_document_history_document_id ON document_history(document_id);
CREATE INDEX IF NOT EXISTS idx_document_history_changed_at ON document_history(changed_at);

-- Update the update_updated_at_column function to also track history
CREATE OR REPLACE FUNCTION track_document_changes()
RETURNS TRIGGER AS $$
DECLARE
    old_values JSONB;
    new_values JSONB;
    change_type VARCHAR(50);
BEGIN
    -- Determine change type
    IF TG_OP = 'INSERT' THEN
        change_type := 'created';
        old_values := NULL;
        new_values := to_jsonb(NEW);
    ELSIF TG_OP = 'UPDATE' THEN
        -- Check what changed
        IF OLD.status IS DISTINCT FROM NEW.status THEN
            change_type := 'status_changed';
        ELSIF OLD.content IS DISTINCT FROM NEW.content OR OLD.title IS DISTINCT FROM NEW.title THEN
            change_type := 'content_updated';
        ELSE
            change_type := 'metadata_updated';
        END IF;
        
        -- Record changed fields only
        old_values := jsonb_build_object(
            'title', OLD.title,
            'status', OLD.status,
            'summary', OLD.summary,
            'metadata', OLD.metadata,
            'relevance_score', OLD.relevance_score
        );
        new_values := jsonb_build_object(
            'title', NEW.title,
            'status', NEW.status,
            'summary', NEW.summary,
            'metadata', NEW.metadata,
            'relevance_score', NEW.relevance_score
        );
    END IF;
    
    -- Insert history record
    INSERT INTO document_history (document_id, source_id, change_type, old_values, new_values)
    VALUES (NEW.id, NEW.source_id, change_type, old_values, new_values);
    
    -- Update the update count
    IF TG_OP = 'UPDATE' THEN
        NEW.update_count := COALESCE(OLD.update_count, 0) + 1;
    END IF;
    
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Create trigger for document changes
DROP TRIGGER IF EXISTS track_document_changes_trigger ON documents;
CREATE TRIGGER track_document_changes_trigger
AFTER INSERT OR UPDATE ON documents
FOR EACH ROW EXECUTE FUNCTION track_document_changes();

-- Function to get documents needing updates
CREATE OR REPLACE FUNCTION get_documents_needing_update(
    source_id_param INTEGER,
    hours_since_check INTEGER DEFAULT 24
)
RETURNS TABLE (
    id INTEGER,
    external_id TEXT,
    last_checked_at TIMESTAMP
) AS $$
BEGIN
    RETURN QUERY
    SELECT d.id, d.external_id, d.last_checked_at
    FROM documents d
    WHERE d.source_id = source_id_param
    AND (
        d.last_checked_at IS NULL 
        OR d.last_checked_at < CURRENT_TIMESTAMP - INTERVAL '1 hour' * hours_since_check
    )
    ORDER BY d.last_checked_at ASC NULLS FIRST
    LIMIT 1000;
END;
$$ LANGUAGE plpgsql;