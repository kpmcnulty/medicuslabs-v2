-- Medical Data Platform - Seed Data
-- This is the SINGLE source of truth for initial data

-- Insert admin user (password: 'admin123')
INSERT INTO admin_users (username, password_hash) VALUES 
('admin', '$2b$12$Fv3SKFQ8tbABF4zJ.6YHN.jKdmho5wPU1IE5DZAHrSeTk.ungVFvi')
ON CONFLICT (username) DO NOTHING;

-- Insert diseases with search terms
INSERT INTO diseases (name, category, synonyms, search_terms) VALUES 
('Multiple Sclerosis', 'neurological', 
    ARRAY['MS', 'disseminated sclerosis', 'encephalomyelitis disseminata'],
    ARRAY['multiple sclerosis', 'MS', 'RRMS', 'PPMS', 'SPMS', 'relapsing remitting', 'primary progressive', 'secondary progressive']
),
('Parkinson''s Disease', 'neurological', 
    ARRAY['PD', 'paralysis agitans', 'shaking palsy'],
    ARRAY['parkinsons', 'parkinson', 'parkinson''s', 'parkinson disease', 'PD', 'parkinsonism']
),
('Alzheimer''s Disease', 'neurological', 
    ARRAY['AD', 'senile dementia'],
    ARRAY['alzheimers', 'alzheimer', 'alzheimer''s', 'alzheimer disease', 'AD', 'dementia']
),
('Amyotrophic Lateral Sclerosis', 'neurological', 
    ARRAY['ALS', 'Lou Gehrig''s disease', 'motor neuron disease'],
    ARRAY['ALS', 'lou gehrig', 'lou gehrig''s', 'amyotrophic lateral sclerosis', 'motor neuron disease']
),
('Lupus', 'autoimmune', 
    ARRAY['SLE', 'systemic lupus erythematosus'],
    ARRAY['lupus', 'SLE', 'systemic lupus', 'systemic lupus erythematosus']
),
('Diabetes Type 1', 'metabolic', 
    ARRAY['T1D', 'juvenile diabetes', 'insulin-dependent diabetes'],
    ARRAY['diabetes', 'diabetic', 'type 1 diabetes', 'T1D', 'diabetes mellitus', 'juvenile diabetes']
),
('Diabetes Type 2', 'metabolic', 
    ARRAY['T2D', 'adult-onset diabetes', 'non-insulin-dependent diabetes'],
    ARRAY['diabetes', 'diabetic', 'type 2 diabetes', 'T2D', 'diabetes mellitus', 'adult onset diabetes']
)
ON CONFLICT (name) DO UPDATE SET
    category = EXCLUDED.category,
    synonyms = EXCLUDED.synonyms,
    search_terms = EXCLUDED.search_terms;

-- Insert sources
INSERT INTO sources (name, category, base_url, scraper_type, association_method, rate_limit, config) VALUES 
-- Search-based sources (search all diseases)
('PubMed', 'publications', 'https://pubmed.ncbi.nlm.nih.gov/', 'pubmed_scraper', 'search', 10, 
    '{"api_key": null, "max_results": 100, "sort_order": "relevance"}'::jsonb),
    
('ClinicalTrials.gov', 'trials', 'https://clinicaltrials.gov/', 'clinicaltrials_scraper', 'search', 10,
    '{"max_results": 50, "status_filter": ["Recruiting", "Active, not recruiting", "Completed"]}'::jsonb),

-- Disease-specific community sources (linked to specific diseases)
('r/MultipleSclerosis', 'community', 'https://www.reddit.com/r/MultipleSclerosis', 'reddit_scraper', 'linked', 60,
    '{"subreddit": "MultipleSclerosis", "post_limit": 50, "include_comments": true, "time_filter": "month"}'::jsonb),
    
('r/ALS', 'community', 'https://www.reddit.com/r/ALS', 'reddit_scraper', 'linked', 60,
    '{"subreddit": "ALS", "post_limit": 50, "include_comments": true, "time_filter": "month"}'::jsonb)

ON CONFLICT (name) DO UPDATE SET
    category = EXCLUDED.category,
    base_url = EXCLUDED.base_url,
    scraper_type = EXCLUDED.scraper_type,
    association_method = EXCLUDED.association_method,
    rate_limit = EXCLUDED.rate_limit,
    config = EXCLUDED.config;

-- Link community sources to their diseases
INSERT INTO source_diseases (source_id, disease_id) VALUES
((SELECT id FROM sources WHERE name = 'r/MultipleSclerosis'), 
 (SELECT id FROM diseases WHERE name = 'Multiple Sclerosis')),
((SELECT id FROM sources WHERE name = 'r/ALS'), 
 (SELECT id FROM diseases WHERE name = 'Amyotrophic Lateral Sclerosis'))
ON CONFLICT DO NOTHING;