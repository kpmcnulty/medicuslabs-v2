-- Migration: Simplify and cleanup duplicated data

-- 1. First, update the association method constraint (from previous migration)
UPDATE sources SET association_method = 'linked' WHERE association_method = 'fixed';
ALTER TABLE sources DROP CONSTRAINT IF EXISTS sources_association_method_check;
ALTER TABLE sources DROP CONSTRAINT IF EXISTS check_association_method;
ALTER TABLE sources ADD CONSTRAINT sources_association_method_check 
    CHECK (association_method IN ('linked', 'search'));

-- 2. Remove sources that reference non-existent diseases (like Diabetes Type 1)
DELETE FROM sources 
WHERE disease_id IS NOT NULL 
  AND disease_id NOT IN (SELECT id FROM diseases);

-- 3. Remove duplicate/unnecessary sources
-- Keep only core sources: PubMed, ClinicalTrials.gov, and one Reddit example
DELETE FROM sources WHERE name IN (
  'r/diabetes',
  'r/diabetes_t1', 
  'Diabetes Daily Forum',
  'MS Society Blog',
  'ALS Forums'
);

-- 4. Update existing Reddit sources to be properly configured
UPDATE sources 
SET association_method = 'linked',
    config = jsonb_build_object(
      'subreddit', 'MultipleSclerosis',
      'post_limit', 100,
      'include_comments', true,
      'sort_by', 'hot'
    )
WHERE name = 'r/MultipleSclerosis';

UPDATE sources 
SET association_method = 'linked',
    config = jsonb_build_object(
      'subreddit', 'MSsupport',
      'post_limit', 100,
      'include_comments', true,
      'sort_by', 'hot'
    )
WHERE name = 'r/MSsupport';

UPDATE sources 
SET association_method = 'linked',
    config = jsonb_build_object(
      'subreddit', 'ALS',
      'post_limit', 100,
      'include_comments', true,
      'sort_by', 'hot'
    )
WHERE name = 'r/ALS';

-- 5. Ensure core search sources are properly configured
UPDATE sources 
SET association_method = 'search',
    disease_id = NULL
WHERE name IN ('PubMed', 'ClinicalTrials.gov');

-- 6. Drop the disease_id column as we're using source_diseases junction table
ALTER TABLE sources DROP COLUMN IF EXISTS disease_id;

-- 7. Ensure proper source-disease associations exist
-- Clear existing associations
DELETE FROM source_diseases;

-- Link MS subreddits to MS
INSERT INTO source_diseases (source_id, disease_id)
SELECT s.id, d.id 
FROM sources s, diseases d
WHERE s.name IN ('r/MultipleSclerosis', 'r/MSsupport') 
  AND d.name = 'Multiple Sclerosis'
ON CONFLICT DO NOTHING;

-- Link ALS subreddit to ALS
INSERT INTO source_diseases (source_id, disease_id)
SELECT s.id, d.id 
FROM sources s, diseases d
WHERE s.name = 'r/ALS' 
  AND d.name = 'Amyotrophic Lateral Sclerosis'
ON CONFLICT DO NOTHING;

-- 8. Add search terms to diseases (if not already there)
UPDATE diseases SET search_terms = CASE
  WHEN name = 'Multiple Sclerosis' THEN 
    ARRAY['multiple sclerosis', 'MS', 'RRMS', 'PPMS', 'SPMS', 'relapsing remitting', 'primary progressive']
  WHEN name = 'Alpha-1 Antitrypsin Deficiency' THEN 
    ARRAY['alpha-1 antitrypsin deficiency', 'AATD', 'alpha-1', 'A1AT deficiency', 'AAT deficiency']
  WHEN name = 'Fabry Disease' THEN 
    ARRAY['fabry disease', 'fabry', 'anderson-fabry disease', 'alpha-galactosidase A deficiency']
  WHEN name = 'Systemic Scleroderma' THEN 
    ARRAY['systemic scleroderma', 'systemic sclerosis', 'SSc', 'scleroderma', 'diffuse scleroderma']
  WHEN name = 'Phenylketonuria' THEN 
    ARRAY['phenylketonuria', 'PKU', 'phenylalanine hydroxylase deficiency', 'folling disease']
  WHEN name = 'Amyotrophic Lateral Sclerosis' THEN 
    ARRAY['ALS', 'amyotrophic lateral sclerosis', 'lou gehrig disease', 'motor neuron disease', 'MND']
  WHEN name = 'Acute Myeloid Leukemia' THEN 
    ARRAY['AML', 'acute myeloid leukemia', 'acute myelogenous leukemia', 'acute nonlymphocytic leukemia']
  ELSE search_terms
END
WHERE search_terms IS NULL OR array_length(search_terms, 1) = 0;

-- 9. Clean up any orphaned data
DELETE FROM crawl_jobs WHERE source_id NOT IN (SELECT id FROM sources);
DELETE FROM documents WHERE source_id NOT IN (SELECT id FROM sources);

-- 10. Final state summary
DO $$
DECLARE
  source_count INTEGER;
  disease_count INTEGER;
  linked_count INTEGER;
  search_count INTEGER;
BEGIN
  SELECT COUNT(*) INTO source_count FROM sources WHERE is_active = true;
  SELECT COUNT(*) INTO disease_count FROM diseases;
  SELECT COUNT(*) INTO linked_count FROM sources WHERE association_method = 'linked';
  SELECT COUNT(*) INTO search_count FROM sources WHERE association_method = 'search';
  
  RAISE NOTICE 'Cleanup complete:';
  RAISE NOTICE '  Active sources: %', source_count;
  RAISE NOTICE '  Diseases: %', disease_count;
  RAISE NOTICE '  Linked sources: %', linked_count;
  RAISE NOTICE '  Search sources: %', search_count;
END $$;