-- Update existing forum sources with proper configuration

-- Update Reddit Medical (id 3)
UPDATE sources 
SET 
    base_url = 'https://www.reddit.com',
    config = '{"scraper_config": "reddit_medical", "requires_js": true, "rate_limit": 0.3}'::jsonb,
    updated_at = CURRENT_TIMESTAMP
WHERE id = 3;

-- Update Patient.info (id 4)
UPDATE sources 
SET 
    base_url = 'https://patient.info',
    config = '{"scraper_config": "patient_info", "requires_js": false, "rate_limit": 0.5}'::jsonb,
    updated_at = CURRENT_TIMESTAMP
WHERE id = 4;

-- Add HealthUnlocked (find next available ID)
INSERT INTO sources (name, type, base_url, config, is_active, created_at, updated_at)
VALUES (
    'HealthUnlocked',
    'secondary',
    'https://healthunlocked.com',
    '{"scraper_config": "healthunlocked", "requires_js": true, "rate_limit": 0.5}'::jsonb,
    true,
    CURRENT_TIMESTAMP,
    CURRENT_TIMESTAMP
) ON CONFLICT (name) DO UPDATE SET
    type = EXCLUDED.type,
    base_url = EXCLUDED.base_url,
    config = EXCLUDED.config,
    updated_at = CURRENT_TIMESTAMP;

-- Update sequence to continue after manual IDs
SELECT setval('sources_id_seq', GREATEST(5, (SELECT MAX(id) FROM sources)), true);