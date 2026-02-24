-- Add new sources for MedicusLabs v2
-- Run this with: docker exec -i medical_data_postgres psql -U medical_user -d medical_data < database/add_new_sources.sql

-- Insert Google News source
INSERT INTO sources (
    name,
    type,
    base_url,
    category,
    scraper_type,
    is_active,
    rate_limit,
    requires_auth,
    association_method,
    config
) VALUES (
    'Google News',
    'rss',
    'https://news.google.com/rss',
    'news',
    'google_news',
    true,
    1.0,
    false,
    'search',
    '{"description": "Google News RSS feed for medical news"}'::jsonb
) ON CONFLICT (name) DO UPDATE SET
    category = EXCLUDED.category,
    scraper_type = EXCLUDED.scraper_type,
    is_active = EXCLUDED.is_active,
    rate_limit = EXCLUDED.rate_limit,
    association_method = EXCLUDED.association_method,
    config = EXCLUDED.config;

-- Insert HealthUnlocked source
INSERT INTO sources (
    name,
    type,
    base_url,
    category,
    scraper_type,
    is_active,
    rate_limit,
    requires_auth,
    association_method,
    config
) VALUES (
    'HealthUnlocked',
    'web',
    'https://healthunlocked.com',
    'community',
    'healthunlocked',
    true,
    0.5,
    false,
    'search',
    '{"description": "HealthUnlocked community discussions"}'::jsonb
) ON CONFLICT (name) DO UPDATE SET
    category = EXCLUDED.category,
    scraper_type = EXCLUDED.scraper_type,
    is_active = EXCLUDED.is_active,
    rate_limit = EXCLUDED.rate_limit,
    association_method = EXCLUDED.association_method,
    config = EXCLUDED.config;

-- Insert Medical News Today source
INSERT INTO sources (
    name,
    type,
    base_url,
    category,
    scraper_type,
    is_active,
    rate_limit,
    requires_auth,
    association_method,
    config
) VALUES (
    'Medical News Today',
    'web',
    'https://www.medicalnewstoday.com',
    'news',
    'medical_news_today',
    true,
    0.5,
    false,
    'search',
    '{"description": "Medical News Today health articles"}'::jsonb
) ON CONFLICT (name) DO UPDATE SET
    category = EXCLUDED.category,
    scraper_type = EXCLUDED.scraper_type,
    is_active = EXCLUDED.is_active,
    rate_limit = EXCLUDED.rate_limit,
    association_method = EXCLUDED.association_method,
    config = EXCLUDED.config;

-- Insert Stack Exchange Health source
INSERT INTO sources (
    name,
    type,
    base_url,
    category,
    scraper_type,
    is_active,
    rate_limit,
    requires_auth,
    association_method,
    config
) VALUES (
    'Stack Exchange Health',
    'api',
    'https://api.stackexchange.com/2.3',
    'community',
    'stackexchange_health',
    true,
    30.0,
    false,
    'search',
    '{"description": "Stack Exchange Health & Medical Sciences Q&A", "sites": ["health", "medicalsciences"]}'::jsonb
) ON CONFLICT (name) DO UPDATE SET
    category = EXCLUDED.category,
    scraper_type = EXCLUDED.scraper_type,
    is_active = EXCLUDED.is_active,
    rate_limit = EXCLUDED.rate_limit,
    association_method = EXCLUDED.association_method,
    config = EXCLUDED.config;

-- Display the new sources
SELECT id, name, category, scraper_type, is_active, rate_limit
FROM sources
WHERE scraper_type IN ('google_news', 'healthunlocked', 'medical_news_today', 'stackexchange_health')
ORDER BY category, name;
