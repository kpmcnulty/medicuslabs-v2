-- Medical Data Platform - Seed Data
-- This is the SINGLE source of truth for initial data

-- Insert admin user (password: 'admin123')
INSERT INTO admin_users (username, password_hash) VALUES 
('admin', '$2b$12$Fv3SKFQ8tbABF4zJ.6YHN.jKdmho5wPU1IE5DZAHrSeTk.ungVFvi')
ON CONFLICT (username) DO NOTHING;

-- Insert diseases with comprehensive search terms
INSERT INTO diseases (name, category, synonyms, search_terms) VALUES 
('Multiple Sclerosis', 'neurological', 
    ARRAY['MS', 'disseminated sclerosis', 'encephalomyelitis disseminata'],
    ARRAY['multiple sclerosis', 'MS', 'RRMS', 'PPMS', 'SPMS', 'relapsing remitting', 'primary progressive', 'secondary progressive']
),
('Amyotrophic Lateral Sclerosis', 'neurological', 
    ARRAY['ALS', 'Lou Gehrig''s disease', 'motor neuron disease', 'MND'],
    ARRAY['ALS', 'amyotrophic lateral sclerosis', 'lou gehrig disease', 'lou gehrigs disease', 'motor neuron disease', 'MND', 'motor neurone disease']
),
('Acute Myeloid Leukemia', 'oncological', 
    ARRAY['AML', 'acute myelogenous leukemia', 'acute nonlymphocytic leukemia', 'acute myeloblastic leukemia'],
    ARRAY['AML', 'acute myeloid leukemia', 'acute myelogenous leukemia', 'acute nonlymphocytic leukemia', 'acute myeloblastic leukemia']
),
('Alpha-1 Antitrypsin Deficiency', 'genetic', 
    ARRAY['AATD', 'A1AT deficiency', 'AAT deficiency', 'alpha-1'],
    ARRAY['alpha-1 antitrypsin deficiency', 'AATD', 'alpha-1', 'A1AT deficiency', 'AAT deficiency', 'alpha 1 antitrypsin']
),
('Fabry Disease', 'genetic', 
    ARRAY['Anderson-Fabry disease', 'alpha-galactosidase A deficiency', 'Fabry''s disease'],
    ARRAY['fabry disease', 'fabry', 'anderson-fabry disease', 'alpha-galactosidase A deficiency', 'fabrys disease']
),
('Phenylketonuria', 'genetic', 
    ARRAY['PKU', 'phenylalanine hydroxylase deficiency', 'Folling disease', 'hyperphenylalaninemia'],
    ARRAY['phenylketonuria', 'PKU', 'phenylalanine hydroxylase deficiency', 'folling disease', 'hyperphenylalaninemia']
)
ON CONFLICT (name) DO UPDATE SET
    category = EXCLUDED.category,
    synonyms = EXCLUDED.synonyms,
    search_terms = EXCLUDED.search_terms;

-- Insert sources
INSERT INTO sources (name, category, base_url, scraper_type, association_method, rate_limit, config) VALUES 
-- Search-based sources (search all diseases)
('PubMed', 'publications', 'https://pubmed.ncbi.nlm.nih.gov/', 'pubmed_api', 'search', 10, 
    '{"api_key": null}'::jsonb),
    
('ClinicalTrials.gov', 'trials', 'https://clinicaltrials.gov/', 'clinicaltrials_api', 'search', 10,
    '{}'::jsonb),

-- Disease-specific community sources (linked to specific diseases)
('r/MultipleSclerosis', 'community', 'https://www.reddit.com/r/MultipleSclerosis', 'reddit_scraper', 'linked', 1,
    '{"subreddit": "MultipleSclerosis", "sort_by": "new", "include_comments": true}'::jsonb),
    
('r/ALS', 'community', 'https://www.reddit.com/r/ALS', 'reddit_scraper', 'linked', 1,
    '{"subreddit": "ALS", "sort_by": "new", "include_comments": true}'::jsonb),

('r/leukemia', 'community', 'https://www.reddit.com/r/leukemia', 'reddit_scraper', 'linked', 1,
    '{"subreddit": "leukemia", "sort_by": "new", "include_comments": true}'::jsonb),

('r/AlphaOne', 'community', 'https://www.reddit.com/r/AlphaOne', 'reddit_scraper', 'linked', 1,
    '{"subreddit": "AlphaOne", "sort_by": "new", "include_comments": true}'::jsonb),

('r/FabryDisease', 'community', 'https://www.reddit.com/r/FabryDisease', 'reddit_scraper', 'linked', 1,
    '{"subreddit": "FabryDisease", "sort_by": "new", "include_comments": true}'::jsonb),

('r/PKU', 'community', 'https://www.reddit.com/r/PKU', 'reddit_scraper', 'linked', 1,
    '{"subreddit": "PKU", "sort_by": "new", "include_comments": true}'::jsonb),

-- Safety data source (search all diseases)
('FDA FAERS', 'safety', 'https://api.fda.gov/drug/event.json', 'faers_api', 'search', 1,
    '{"api_key": null, "update_window_hours": 168, "max_results_per_disease": 100}'::jsonb)

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
 (SELECT id FROM diseases WHERE name = 'Amyotrophic Lateral Sclerosis')),
((SELECT id FROM sources WHERE name = 'r/leukemia'), 
 (SELECT id FROM diseases WHERE name = 'Acute Myeloid Leukemia')),
((SELECT id FROM sources WHERE name = 'r/AlphaOne'), 
 (SELECT id FROM diseases WHERE name = 'Alpha-1 Antitrypsin Deficiency')),
((SELECT id FROM sources WHERE name = 'r/FabryDisease'), 
 (SELECT id FROM diseases WHERE name = 'Fabry Disease')),
((SELECT id FROM sources WHERE name = 'r/PKU'), 
 (SELECT id FROM diseases WHERE name = 'Phenylketonuria'))
ON CONFLICT DO NOTHING;