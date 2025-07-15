-- Fix incorrect disease associations from search-based sources
-- This migration removes incorrect associations where search sources linked to all diseases

-- First, let's see what we're dealing with
-- Check documents with multiple disease associations from search sources
SELECT 
    s.name as source_name,
    s.association_method,
    d.external_id,
    d.title,
    COUNT(dd.disease_id) as disease_count,
    STRING_AGG(dis.name, ', ') as linked_diseases
FROM documents d
JOIN sources s ON d.source_id = s.id
JOIN document_diseases dd ON d.id = dd.document_id
JOIN diseases dis ON dd.disease_id = dis.id
WHERE s.association_method = 'search'
GROUP BY s.name, s.association_method, d.id, d.external_id, d.title
HAVING COUNT(dd.disease_id) > 1
LIMIT 20;

-- Option 1: CLEAN APPROACH - Remove all disease associations for search sources
-- Then re-run scrapers with corrected logic
BEGIN;

-- Delete all disease associations for documents from search sources
DELETE FROM document_diseases 
WHERE document_id IN (
    SELECT d.id 
    FROM documents d
    JOIN sources s ON d.source_id = s.id
    WHERE s.association_method = 'search'
);

-- Count affected documents
SELECT COUNT(DISTINCT d.id) as documents_to_reprocess
FROM documents d
JOIN sources s ON d.source_id = s.id
WHERE s.association_method = 'search';

COMMIT;

-- Option 2: SELECTIVE APPROACH - Try to guess correct association
-- Based on document title/content matching disease names
-- This is less reliable but preserves some data

-- Example: Fix Multiple Sclerosis associations
UPDATE document_diseases dd
SET disease_id = (
    SELECT id FROM diseases WHERE name = 'Multiple Sclerosis' LIMIT 1
)
FROM documents d
JOIN sources s ON d.source_id = s.id
WHERE dd.document_id = d.id
  AND s.association_method = 'search'
  AND (
    LOWER(d.title) LIKE '%multiple sclerosis%' OR
    LOWER(d.title) LIKE '%ms %' OR
    LOWER(d.content) LIKE '%multiple sclerosis%'
  );

-- Option 3: FULL RESET - Delete all documents from search sources
-- Most thorough but requires complete re-scraping
BEGIN;

-- Delete all documents from search sources
DELETE FROM documents 
WHERE source_id IN (
    SELECT id FROM sources WHERE association_method = 'search'
);

-- This will cascade delete from document_diseases, document_metadata, etc.

COMMIT;