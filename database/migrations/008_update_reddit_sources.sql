-- Update existing Reddit source to be a search-based source (generic)
UPDATE sources 
SET association_method = 'search',
    name = 'Reddit (Search)',
    default_config = jsonb_build_object(
        'post_limit', 50,
        'include_comments', true,
        'comment_limit', 10,
        'sort_by', 'hot'
    )
WHERE name = 'Reddit Medical';

-- Add specific subreddit sources as fixed sources
INSERT INTO sources (name, category, base_url, scraper_type, rate_limit, is_active, association_method, config, default_config) VALUES
-- Multiple Sclerosis subreddit
('r/MultipleSclerosis', 'community', 'https://www.reddit.com/r/MultipleSclerosis', 'reddit_scraper', 60, true, 'fixed', 
    jsonb_build_object('subreddit', 'MultipleSclerosis'),
    jsonb_build_object('post_limit', 50, 'include_comments', true, 'comment_limit', 10, 'sort_by', 'hot')
),

-- Diabetes subreddit
('r/diabetes', 'community', 'https://www.reddit.com/r/diabetes', 'reddit_scraper', 60, true, 'fixed',
    jsonb_build_object('subreddit', 'diabetes'),
    jsonb_build_object('post_limit', 50, 'include_comments', true, 'comment_limit', 10, 'sort_by', 'hot')
),

-- Type 1 Diabetes subreddit
('r/diabetes_t1', 'community', 'https://www.reddit.com/r/diabetes_t1', 'reddit_scraper', 60, true, 'fixed',
    jsonb_build_object('subreddit', 'diabetes_t1'),
    jsonb_build_object('post_limit', 50, 'include_comments', true, 'comment_limit', 10, 'sort_by', 'hot')
),

-- Lupus subreddit
('r/lupus', 'community', 'https://www.reddit.com/r/lupus', 'reddit_scraper', 60, true, 'fixed',
    jsonb_build_object('subreddit', 'lupus'),
    jsonb_build_object('post_limit', 50, 'include_comments', true, 'comment_limit', 10, 'sort_by', 'hot')
),

-- Parkinson's Disease subreddit
('r/Parkinsons', 'community', 'https://www.reddit.com/r/Parkinsons', 'reddit_scraper', 60, true, 'fixed',
    jsonb_build_object('subreddit', 'Parkinsons'),
    jsonb_build_object('post_limit', 50, 'include_comments', true, 'comment_limit', 10, 'sort_by', 'hot')
),

-- Alzheimer's subreddit
('r/Alzheimers', 'community', 'https://www.reddit.com/r/Alzheimers', 'reddit_scraper', 60, true, 'fixed',
    jsonb_build_object('subreddit', 'Alzheimers'),
    jsonb_build_object('post_limit', 50, 'include_comments', true, 'comment_limit', 10, 'sort_by', 'hot')
),

-- Chronic Pain subreddit
('r/ChronicPain', 'community', 'https://www.reddit.com/r/ChronicPain', 'reddit_scraper', 60, true, 'fixed',
    jsonb_build_object('subreddit', 'ChronicPain'),
    jsonb_build_object('post_limit', 50, 'include_comments', true, 'comment_limit', 10, 'sort_by', 'hot')
),

-- Migraine subreddit
('r/migraine', 'community', 'https://www.reddit.com/r/migraine', 'reddit_scraper', 60, true, 'fixed',
    jsonb_build_object('subreddit', 'migraine'),
    jsonb_build_object('post_limit', 50, 'include_comments', true, 'comment_limit', 10, 'sort_by', 'hot')
)
ON CONFLICT (name) DO NOTHING;

-- Link the subreddits to their relevant diseases
-- First, get the disease IDs
DO $$
DECLARE
    ms_id INTEGER;
    diabetes_id INTEGER;
    lupus_id INTEGER;
    parkinsons_id INTEGER;
    alzheimers_id INTEGER;
    chronic_pain_id INTEGER;
    migraine_id INTEGER;
    
    ms_subreddit_id INTEGER;
    diabetes_subreddit_id INTEGER;
    diabetes_t1_subreddit_id INTEGER;
    lupus_subreddit_id INTEGER;
    parkinsons_subreddit_id INTEGER;
    alzheimers_subreddit_id INTEGER;
    chronic_pain_subreddit_id INTEGER;
    migraine_subreddit_id INTEGER;
BEGIN
    -- Get disease IDs (these should exist from seeds)
    SELECT id INTO ms_id FROM diseases WHERE name = 'Multiple Sclerosis';
    SELECT id INTO diabetes_id FROM diseases WHERE name = 'Diabetes';
    SELECT id INTO lupus_id FROM diseases WHERE name = 'Lupus';
    SELECT id INTO parkinsons_id FROM diseases WHERE name = 'Parkinson''s Disease';
    SELECT id INTO alzheimers_id FROM diseases WHERE name = 'Alzheimer''s Disease';
    SELECT id INTO chronic_pain_id FROM diseases WHERE name = 'Chronic Pain';
    SELECT id INTO migraine_id FROM diseases WHERE name = 'Migraine';
    
    -- Get source IDs for the subreddits
    SELECT id INTO ms_subreddit_id FROM sources WHERE name = 'r/MultipleSclerosis';
    SELECT id INTO diabetes_subreddit_id FROM sources WHERE name = 'r/diabetes';
    SELECT id INTO diabetes_t1_subreddit_id FROM sources WHERE name = 'r/diabetes_t1';
    SELECT id INTO lupus_subreddit_id FROM sources WHERE name = 'r/lupus';
    SELECT id INTO parkinsons_subreddit_id FROM sources WHERE name = 'r/Parkinsons';
    SELECT id INTO alzheimers_subreddit_id FROM sources WHERE name = 'r/Alzheimers';
    SELECT id INTO chronic_pain_subreddit_id FROM sources WHERE name = 'r/ChronicPain';
    SELECT id INTO migraine_subreddit_id FROM sources WHERE name = 'r/migraine';
    
    -- Link sources to diseases
    IF ms_id IS NOT NULL AND ms_subreddit_id IS NOT NULL THEN
        INSERT INTO source_diseases (source_id, disease_id) VALUES (ms_subreddit_id, ms_id) ON CONFLICT DO NOTHING;
    END IF;
    
    IF diabetes_id IS NOT NULL THEN
        IF diabetes_subreddit_id IS NOT NULL THEN
            INSERT INTO source_diseases (source_id, disease_id) VALUES (diabetes_subreddit_id, diabetes_id) ON CONFLICT DO NOTHING;
        END IF;
        IF diabetes_t1_subreddit_id IS NOT NULL THEN
            INSERT INTO source_diseases (source_id, disease_id) VALUES (diabetes_t1_subreddit_id, diabetes_id) ON CONFLICT DO NOTHING;
        END IF;
    END IF;
    
    IF lupus_id IS NOT NULL AND lupus_subreddit_id IS NOT NULL THEN
        INSERT INTO source_diseases (source_id, disease_id) VALUES (lupus_subreddit_id, lupus_id) ON CONFLICT DO NOTHING;
    END IF;
    
    IF parkinsons_id IS NOT NULL AND parkinsons_subreddit_id IS NOT NULL THEN
        INSERT INTO source_diseases (source_id, disease_id) VALUES (parkinsons_subreddit_id, parkinsons_id) ON CONFLICT DO NOTHING;
    END IF;
    
    IF alzheimers_id IS NOT NULL AND alzheimers_subreddit_id IS NOT NULL THEN
        INSERT INTO source_diseases (source_id, disease_id) VALUES (alzheimers_subreddit_id, alzheimers_id) ON CONFLICT DO NOTHING;
    END IF;
    
    IF chronic_pain_id IS NOT NULL AND chronic_pain_subreddit_id IS NOT NULL THEN
        INSERT INTO source_diseases (source_id, disease_id) VALUES (chronic_pain_subreddit_id, chronic_pain_id) ON CONFLICT DO NOTHING;
    END IF;
    
    IF migraine_id IS NOT NULL AND migraine_subreddit_id IS NOT NULL THEN
        INSERT INTO source_diseases (source_id, disease_id) VALUES (migraine_subreddit_id, migraine_id) ON CONFLICT DO NOTHING;
    END IF;
END $$;