-- Add FDA FAERS as a new data source
-- This is a search-based source that searches across all diseases

-- Insert FAERS source
INSERT INTO sources (name, category, base_url, scraper_type, association_method, rate_limit, config, is_active) VALUES 
('FDA FAERS', 'safety', 'https://api.fda.gov/drug/event.json', 'faers_api', 'search', 1,
    '{"api_key": null, "update_window_hours": 168, "max_results_per_disease": 100}'::jsonb, true)
ON CONFLICT (name) DO UPDATE SET
    category = EXCLUDED.category,
    base_url = EXCLUDED.base_url,
    scraper_type = EXCLUDED.scraper_type,
    association_method = EXCLUDED.association_method,
    rate_limit = EXCLUDED.rate_limit,
    config = EXCLUDED.config,
    is_active = EXCLUDED.is_active;

-- Add a comment explaining what FAERS is
COMMENT ON COLUMN sources.name IS 'FDA Adverse Event Reporting System (FAERS) contains adverse event and medication error reports submitted to FDA';