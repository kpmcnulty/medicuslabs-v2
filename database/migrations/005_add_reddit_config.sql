-- Migration to add Reddit disease-subreddit configuration
-- This updates the Reddit Medical source with disease-specific subreddit mappings

UPDATE sources 
SET default_config = jsonb_build_object(
    'reddit_client_id', 'from_env',
    'reddit_client_secret', 'from_env',
    'reddit_user_agent', 'MedicusLabs/1.0',
    'disease_subreddits', jsonb_build_object(
        'multiple sclerosis', ARRAY['MultipleSclerosis', 'MSsupport', 'multiplesclerosis'],
        'alpha-1 antitrypsin deficiency', ARRAY['Alpha1', 'AATD', 'Alpha1Antitrypsin'],
        'fabry disease', ARRAY['FabrysDisease', 'rarediseases'],
        'systemic scleroderma', ARRAY['scleroderma', 'Autoimmune', 'rheumatology'],
        'phenylketonuria', ARRAY['PKU', 'rarediseases', 'metabolicdisorders'],
        'amyotrophic lateral sclerosis', ARRAY['ALS', 'MND', 'als'],
        'acute myeloid leukemia', ARRAY['leukemia', 'AML', 'cancer', 'CancerSurvivors']
    ),
    'post_limit', 50,
    'initial_limit', 100,
    'incremental_limit', 25,
    'include_comments', true,
    'comment_limit', 10,
    'sort_by', 'hot',
    'update_window_hours', 12
)
WHERE name = 'Reddit Medical';

-- Add comment explaining the configuration
COMMENT ON COLUMN sources.default_config IS 'Default configuration for this source. For Reddit, includes disease-subreddit mappings for targeted scraping.';