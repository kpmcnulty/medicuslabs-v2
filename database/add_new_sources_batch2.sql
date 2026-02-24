-- Add 5 new sources for MedicusLabs: bioRxiv/medRxiv, OpenFDA, WHO DON, Wikipedia, Drugs.com

-- 1. bioRxiv/medRxiv Preprints
INSERT INTO sources (name, category, base_url, scraper_type, rate_limit, is_active, association_method, config)
VALUES (
    'bioRxiv/medRxiv',
    'publications',
    'https://api.biorxiv.org',
    'biorxiv',
    1.0,
    true,
    'search',
    '{"description": "Medical preprints from medRxiv", "update_window_hours": 168}'::jsonb
)
ON CONFLICT (name) DO UPDATE SET
    category = EXCLUDED.category,
    base_url = EXCLUDED.base_url,
    scraper_type = EXCLUDED.scraper_type,
    rate_limit = EXCLUDED.rate_limit,
    is_active = EXCLUDED.is_active,
    association_method = EXCLUDED.association_method,
    config = EXCLUDED.config,
    updated_at = CURRENT_TIMESTAMP;

-- 2. OpenFDA Drug Labels
INSERT INTO sources (name, category, base_url, scraper_type, rate_limit, is_active, association_method, config)
VALUES (
    'OpenFDA Drug Labels',
    'safety',
    'https://api.fda.gov/drug/label.json',
    'openfda',
    4.0,
    true,
    'search',
    '{"description": "FDA drug label information", "update_window_hours": 720}'::jsonb
)
ON CONFLICT (name) DO UPDATE SET
    category = EXCLUDED.category,
    base_url = EXCLUDED.base_url,
    scraper_type = EXCLUDED.scraper_type,
    rate_limit = EXCLUDED.rate_limit,
    is_active = EXCLUDED.is_active,
    association_method = EXCLUDED.association_method,
    config = EXCLUDED.config,
    updated_at = CURRENT_TIMESTAMP;

-- 3. WHO Disease Outbreak News
INSERT INTO sources (name, category, base_url, scraper_type, rate_limit, is_active, association_method, config)
VALUES (
    'WHO Disease Outbreak News',
    'news',
    'https://www.who.int/feeds/entity/don/en/rss.xml',
    'who_don',
    0.5,
    true,
    'search',
    '{"description": "World Health Organization disease outbreak news", "update_window_hours": 24}'::jsonb
)
ON CONFLICT (name) DO UPDATE SET
    category = EXCLUDED.category,
    base_url = EXCLUDED.base_url,
    scraper_type = EXCLUDED.scraper_type,
    rate_limit = EXCLUDED.rate_limit,
    is_active = EXCLUDED.is_active,
    association_method = EXCLUDED.association_method,
    config = EXCLUDED.config,
    updated_at = CURRENT_TIMESTAMP;

-- 4. Wikipedia Medical
INSERT INTO sources (name, category, base_url, scraper_type, rate_limit, is_active, association_method, config)
VALUES (
    'Wikipedia Medical',
    'publications',
    'https://en.wikipedia.org/api/rest_v1',
    'wikipedia',
    1.0,
    true,
    'search',
    '{"description": "Wikipedia medical reference articles", "update_window_hours": 168}'::jsonb
)
ON CONFLICT (name) DO UPDATE SET
    category = EXCLUDED.category,
    base_url = EXCLUDED.base_url,
    scraper_type = EXCLUDED.scraper_type,
    rate_limit = EXCLUDED.rate_limit,
    is_active = EXCLUDED.is_active,
    association_method = EXCLUDED.association_method,
    config = EXCLUDED.config,
    updated_at = CURRENT_TIMESTAMP;

-- 5. Drugs.com
INSERT INTO sources (name, category, base_url, scraper_type, rate_limit, is_active, association_method, config)
VALUES (
    'Drugs.com',
    'safety',
    'https://www.drugs.com',
    'drugscom',
    0.5,
    true,
    'search',
    '{"description": "Drug information and safety data", "update_window_hours": 720}'::jsonb
)
ON CONFLICT (name) DO UPDATE SET
    category = EXCLUDED.category,
    base_url = EXCLUDED.base_url,
    scraper_type = EXCLUDED.scraper_type,
    rate_limit = EXCLUDED.rate_limit,
    is_active = EXCLUDED.is_active,
    association_method = EXCLUDED.association_method,
    config = EXCLUDED.config,
    updated_at = CURRENT_TIMESTAMP;
