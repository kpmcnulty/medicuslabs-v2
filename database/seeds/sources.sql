-- Simplified source configuration
-- Only core sources that work and make sense for our 7 diseases

-- Search-based sources (search for disease terms across all content)
INSERT INTO sources (name, category, base_url, scraper_type, rate_limit, association_method, config) VALUES
('PubMed', 'publications', 'https://pubmed.ncbi.nlm.nih.gov', 'pubmed_api', 10, 'search', 
  '{"results_per_disease": 50, "date_range": "1year"}'::jsonb),
('ClinicalTrials.gov', 'trials', 'https://clinicaltrials.gov', 'clinicaltrials_api', 10, 'search',
  '{"results_per_disease": 25, "include_recruiting": true}'::jsonb)
ON CONFLICT (name) DO UPDATE SET 
  association_method = EXCLUDED.association_method,
  config = EXCLUDED.config;

-- Note: Disease-specific sources like r/MultipleSclerosis should be added via the admin portal
-- This keeps the seed data minimal and allows flexibility in source management