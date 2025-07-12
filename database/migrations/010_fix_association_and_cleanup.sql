-- Migration: Fix association method and cleanup sources properly

-- 1. First check what association_method values exist
SELECT DISTINCT association_method FROM sources;

-- 2. Update any null or invalid association_method values
UPDATE sources 
SET association_method = CASE
  WHEN name IN ('PubMed', 'ClinicalTrials.gov') THEN 'search'
  WHEN name LIKE 'r/%' OR name LIKE '%reddit%' OR name LIKE '%Reddit%' THEN 'linked'
  WHEN association_method IS NULL THEN 'search'
  ELSE association_method
END
WHERE association_method IS NULL 
   OR association_method NOT IN ('linked', 'search');

-- 3. Now update 'fixed' to 'linked'
UPDATE sources SET association_method = 'linked' WHERE association_method = 'fixed';

-- 4. Drop and recreate the constraint
ALTER TABLE sources DROP CONSTRAINT IF EXISTS sources_association_method_check;
ALTER TABLE sources DROP CONSTRAINT IF EXISTS check_association_method;

-- Ensure all sources have valid values before adding constraint
UPDATE sources SET association_method = 'search' 
WHERE association_method NOT IN ('linked', 'search');

ALTER TABLE sources ADD CONSTRAINT sources_association_method_check 
    CHECK (association_method IN ('linked', 'search'));

-- 5. Check if search_terms column exists on diseases
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns 
                   WHERE table_name = 'diseases' 
                   AND column_name = 'search_terms') THEN
        ALTER TABLE diseases ADD COLUMN search_terms TEXT[] DEFAULT ARRAY[]::TEXT[];
    END IF;
END $$;

-- 6. Update search terms for diseases
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
  ELSE COALESCE(search_terms, ARRAY[]::TEXT[])
END
WHERE search_terms IS NULL OR array_length(search_terms, 1) = 0;

-- 7. Clean up sources - remove non-working ones
DELETE FROM sources 
WHERE name IN ('HealthUnlocked', 'Patient.info Forums', 'Reddit Medical')
  AND scraper_type = 'web_scraper';

-- 8. Update core sources to proper configuration
UPDATE sources 
SET association_method = 'search',
    config = '{"results_per_disease": 50, "date_range": "1year"}'::jsonb
WHERE name = 'PubMed';

UPDATE sources 
SET association_method = 'search',
    config = '{"results_per_disease": 25, "include_recruiting": true}'::jsonb
WHERE name = 'ClinicalTrials.gov';

-- 9. Update Reddit sources
UPDATE sources 
SET association_method = 'linked',
    config = jsonb_build_object(
      'subreddit', CASE
        WHEN name = 'r/MultipleSclerosis' THEN 'MultipleSclerosis'
        WHEN name = 'Reddit - r/MultipleSclerosis' THEN 'MultipleSclerosis'
        WHEN name = 'r/ALS' THEN 'ALS'
        ELSE regexp_replace(name, '^(Reddit - )?r/', '')
      END,
      'post_limit', 100,
      'include_comments', true,
      'sort_by', 'hot'
    )
WHERE name LIKE '%r/%' OR name LIKE 'Reddit%';

-- 10. Clean up duplicate Reddit sources
DELETE FROM sources s1
WHERE EXISTS (
  SELECT 1 FROM sources s2
  WHERE s2.name LIKE '%' || regexp_replace(s1.name, '^(Reddit - )?r/', '') || '%'
    AND s2.id < s1.id
    AND s2.scraper_type = 'reddit_scraper'
);

-- 11. Set up source-disease associations
DELETE FROM source_diseases;

-- Link MS subreddits to MS
INSERT INTO source_diseases (source_id, disease_id)
SELECT s.id, d.id 
FROM sources s, diseases d
WHERE (s.name LIKE '%MultipleSclerosis%' OR s.name LIKE '%MSsupport%')
  AND d.name = 'Multiple Sclerosis'
  AND s.association_method = 'linked'
ON CONFLICT DO NOTHING;

-- Link ALS subreddit to ALS
INSERT INTO source_diseases (source_id, disease_id)
SELECT s.id, d.id 
FROM sources s, diseases d
WHERE s.name LIKE '%ALS%'
  AND d.name = 'Amyotrophic Lateral Sclerosis'
  AND s.association_method = 'linked'
ON CONFLICT DO NOTHING;

-- 12. Final cleanup and status
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
  
  -- Show current sources
  RAISE NOTICE '';
  RAISE NOTICE 'Current sources:';
  FOR r IN SELECT name, association_method, scraper_type FROM sources WHERE is_active = true ORDER BY name
  LOOP
    RAISE NOTICE '  - % (%) [%]', r.name, r.association_method, r.scraper_type;
  END LOOP;
END $$;