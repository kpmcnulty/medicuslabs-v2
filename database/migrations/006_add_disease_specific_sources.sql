-- Migration to add disease-specific sources
-- This allows tracking individual subreddits, blogs, and forums per disease

-- First, let's add a disease_id column to sources to link sources to specific diseases
ALTER TABLE sources ADD COLUMN disease_id INTEGER REFERENCES diseases(id);

-- Add an index for performance
CREATE INDEX idx_sources_disease_id ON sources(disease_id);

-- Now let's add some disease-specific sources as examples
-- These would be added through the admin UI in practice

-- Multiple Sclerosis sources
INSERT INTO sources (name, category, base_url, scraper_type, rate_limit, disease_id, config) 
VALUES 
('r/MultipleSclerosis', 'community', 'https://www.reddit.com/r/MultipleSclerosis', 'reddit_scraper', 60, 
    (SELECT id FROM diseases WHERE name = 'Multiple Sclerosis'), 
    '{"subreddit": "MultipleSclerosis", "post_limit": 50, "include_comments": true}'::jsonb),
    
('r/MSsupport', 'community', 'https://www.reddit.com/r/MSsupport', 'reddit_scraper', 60,
    (SELECT id FROM diseases WHERE name = 'Multiple Sclerosis'),
    '{"subreddit": "MSsupport", "post_limit": 25, "include_comments": true}'::jsonb),
    
('MS Society Blog', 'publications', 'https://www.nationalmssociety.org/blog', 'web_scraper', 30,
    (SELECT id FROM diseases WHERE name = 'Multiple Sclerosis'),
    '{"selector": "article.blog-post", "date_format": "MMMM DD, YYYY"}'::jsonb);

-- Diabetes sources
INSERT INTO sources (name, category, base_url, scraper_type, rate_limit, disease_id, config)
VALUES
('r/diabetes', 'community', 'https://www.reddit.com/r/diabetes', 'reddit_scraper', 60,
    (SELECT id FROM diseases WHERE name = 'Diabetes Type 1'),
    '{"subreddit": "diabetes", "post_limit": 50, "include_comments": true}'::jsonb),
    
('r/diabetes_t1', 'community', 'https://www.reddit.com/r/diabetes_t1', 'reddit_scraper', 60,
    (SELECT id FROM diseases WHERE name = 'Diabetes Type 1'),
    '{"subreddit": "diabetes_t1", "post_limit": 50, "include_comments": true}'::jsonb),
    
('Diabetes Daily Forum', 'community', 'https://www.diabetesdaily.com/forum/', 'web_scraper', 30,
    (SELECT id FROM diseases WHERE name = 'Diabetes Type 1'),
    '{"forum_sections": ["type-1-diabetes", "cgm", "insulin-pumps"]}'::jsonb);

-- ALS sources
INSERT INTO sources (name, category, base_url, scraper_type, rate_limit, disease_id, config)
VALUES
('r/ALS', 'community', 'https://www.reddit.com/r/ALS', 'reddit_scraper', 60,
    (SELECT id FROM diseases WHERE name = 'Amyotrophic Lateral Sclerosis'),
    '{"subreddit": "ALS", "post_limit": 50, "include_comments": true}'::jsonb),
    
('ALS Forums', 'community', 'https://www.alsforums.com/', 'web_scraper', 30,
    (SELECT id FROM diseases WHERE name = 'Amyotrophic Lateral Sclerosis'),
    '{"forum_id": "PALS", "max_pages": 5}'::jsonb);

-- Update the sources table comment
COMMENT ON COLUMN sources.disease_id IS 'Optional link to a specific disease. NULL for general medical sources like PubMed.';
COMMENT ON COLUMN sources.config IS 'Source-specific configuration. For Reddit: subreddit name. For web scrapers: CSS selectors, pagination rules, etc.';