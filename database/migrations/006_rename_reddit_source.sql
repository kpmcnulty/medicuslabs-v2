-- Rename Reddit Medical to just Reddit for clarity
UPDATE sources 
SET name = 'Reddit'
WHERE name = 'Reddit Medical';

-- Update any existing Reddit documents to ensure consistency
-- (This is a no-op if the source_id remains the same)