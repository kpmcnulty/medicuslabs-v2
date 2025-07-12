-- Simplified source configuration
-- Only core sources that make sense for our 7 diseases

-- Search-based sources (search for disease terms)
INSERT INTO sources (name, category, base_url, scraper_type, rate_limit, association_method, config) VALUES
('PubMed', 'publications', 'https://pubmed.ncbi.nlm.nih.gov', 'pubmed_api', 10, 'search', 
  '{"results_per_disease": 50, "date_range": "1year"}'::jsonb),
('ClinicalTrials.gov', 'trials', 'https://clinicaltrials.gov', 'clinicaltrials_api', 10, 'search',
  '{"results_per_disease": 25, "include_recruiting": true}'::jsonb)
ON CONFLICT (name) DO UPDATE SET 
  association_method = EXCLUDED.association_method,
  config = EXCLUDED.config;

-- Linked sources (disease-specific communities)
-- Only add these for diseases that actually have active communities
INSERT INTO sources (name, category, base_url, scraper_type, rate_limit, association_method, config) VALUES
-- Multiple Sclerosis has active communities
('r/MultipleSclerosis', 'community', 'https://www.reddit.com/r/MultipleSclerosis', 'reddit_scraper', 60, 'linked',
  '{"subreddit": "MultipleSclerosis", "post_limit": 100, "include_comments": true, "sort_by": "hot"}'::jsonb),
-- ALS has an active community  
('r/ALS', 'community', 'https://www.reddit.com/r/ALS', 'reddit_scraper', 60, 'linked',
  '{"subreddit": "ALS", "post_limit": 100, "include_comments": true, "sort_by": "hot"}'::jsonb)
ON CONFLICT (name) DO UPDATE SET 
  association_method = EXCLUDED.association_method,
  config = EXCLUDED.config;

-- Link disease-specific sources to their diseases
INSERT INTO source_diseases (source_id, disease_id)
SELECT s.id, d.id FROM sources s, diseases d
WHERE s.name = 'r/MultipleSclerosis' AND d.name = 'Multiple Sclerosis'
ON CONFLICT DO NOTHING;

INSERT INTO source_diseases (source_id, disease_id)
SELECT s.id, d.id FROM sources s, diseases d
WHERE s.name = 'r/ALS' AND d.name = 'Amyotrophic Lateral Sclerosis'
ON CONFLICT DO NOTHING;