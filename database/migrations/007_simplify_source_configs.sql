-- Migration: Simplify source configuration and add search terms

-- 1. Add search_terms to diseases table
ALTER TABLE diseases ADD COLUMN IF NOT EXISTS search_terms TEXT[] DEFAULT ARRAY[]::TEXT[];

-- 2. Add association_method to sources if not exists
ALTER TABLE sources ADD COLUMN IF NOT EXISTS association_method VARCHAR(20) DEFAULT 'search';

-- 3. Drop the confusing default_config column if it exists
ALTER TABLE sources DROP COLUMN IF EXISTS default_config;

-- 4. Add constraint for association_method
ALTER TABLE sources DROP CONSTRAINT IF EXISTS sources_association_method_check;
ALTER TABLE sources ADD CONSTRAINT sources_association_method_check 
    CHECK (association_method IN ('linked', 'search'));

-- 5. Populate search terms for existing diseases
UPDATE diseases SET search_terms = ARRAY['multiple sclerosis', 'MS', 'RRMS', 'PPMS', 'SPMS', 'relapsing remitting', 'primary progressive', 'secondary progressive'] 
WHERE name = 'Multiple Sclerosis';

UPDATE diseases SET search_terms = ARRAY['parkinsons', 'parkinson', 'parkinson''s', 'parkinson disease', 'PD', 'parkinsonism'] 
WHERE name = 'Parkinson''s Disease';

UPDATE diseases SET search_terms = ARRAY['alzheimers', 'alzheimer', 'alzheimer''s', 'alzheimer disease', 'AD', 'dementia'] 
WHERE name = 'Alzheimer''s Disease';

UPDATE diseases SET search_terms = ARRAY['lupus', 'SLE', 'systemic lupus', 'systemic lupus erythematosus'] 
WHERE name = 'Lupus';

UPDATE diseases SET search_terms = ARRAY['ALS', 'lou gehrig', 'lou gehrig''s', 'amyotrophic lateral sclerosis', 'motor neuron disease'] 
WHERE name = 'Amyotrophic Lateral Sclerosis';

UPDATE diseases SET search_terms = ARRAY['diabetes', 'diabetic', 'type 1 diabetes', 'type 2 diabetes', 'T1D', 'T2D', 'diabetes mellitus'] 
WHERE name = 'Diabetes Type 1';

UPDATE diseases SET search_terms = ARRAY['diabetes', 'diabetic', 'type 2 diabetes', 'T2D', 'diabetes mellitus', 'adult onset diabetes'] 
WHERE name = 'Diabetes Type 2';

UPDATE diseases SET search_terms = ARRAY['depression', 'depressive', 'major depression', 'clinical depression', 'MDD', 'major depressive disorder'] 
WHERE name = 'Depression';

UPDATE diseases SET search_terms = ARRAY['anxiety', 'anxiety disorder', 'GAD', 'generalized anxiety', 'panic disorder', 'social anxiety'] 
WHERE name = 'Anxiety Disorders';

UPDATE diseases SET search_terms = ARRAY['PTSD', 'post traumatic stress', 'post-traumatic stress', 'trauma disorder'] 
WHERE name = 'Post-Traumatic Stress Disorder';

UPDATE diseases SET search_terms = ARRAY['bipolar', 'bipolar disorder', 'manic depression', 'BD', 'bipolar I', 'bipolar II'] 
WHERE name = 'Bipolar Disorder';

-- 6. Update existing Reddit sources to be 'linked' type with proper config
UPDATE sources 
SET association_method = 'linked',
    config = jsonb_build_object(
        'subreddit', CASE 
            WHEN name LIKE '%MultipleSclerosis%' THEN 'MultipleSclerosis'
            WHEN name LIKE '%MSsupport%' THEN 'MSsupport'
            WHEN name LIKE '%Parkinsons%' THEN 'Parkinsons'
            WHEN name LIKE '%diabetes_t1%' THEN 'diabetes_t1'
            WHEN name LIKE '%diabetes' AND name NOT LIKE '%_t1%' THEN 'diabetes'
            WHEN name LIKE '%ALS%' THEN 'ALS'
            ELSE 'medical'
        END,
        'post_limit', 100,
        'include_comments', true,
        'sort_by', 'hot'
    )
WHERE scraper_type = 'reddit_scraper' AND disease_id IS NOT NULL;

-- 7. Update PubMed and ClinicalTrials to be 'search' type
UPDATE sources 
SET association_method = 'search',
    disease_id = NULL
WHERE name IN ('PubMed', 'ClinicalTrials.gov');

-- 8. Add comments
COMMENT ON COLUMN diseases.search_terms IS 'Array of search terms, synonyms, and abbreviations for this disease';
COMMENT ON COLUMN sources.association_method IS 'How this source relates to diseases: linked = fixed to specific diseases, search = searches for disease terms';