-- Add primary sources
INSERT INTO sources (id, name, type, base_url, config, is_active, crawl_state) VALUES
(1, 'ClinicalTrials.gov', 'primary', 'https://clinicaltrials.gov', '{}', true, '{}'),
(2, 'PubMed', 'primary', 'https://pubmed.ncbi.nlm.nih.gov', '{}', true, '{}')
ON CONFLICT (id) DO UPDATE SET
    name = EXCLUDED.name,
    type = EXCLUDED.type,
    base_url = EXCLUDED.base_url,
    is_active = EXCLUDED.is_active;

-- Add secondary sources (forums)
INSERT INTO sources (id, name, type, base_url, config, is_active, crawl_state) VALUES
(3, 'HealthUnlocked', 'secondary', 'https://healthunlocked.com', '{"scraper_config": "healthunlocked"}', true, '{}'),
(4, 'Patient.info Forums', 'secondary', 'https://patient.info', '{"scraper_config": "patient_info"}', true, '{}'),
(5, 'Reddit Medical', 'secondary', 'https://reddit.com', '{"scraper_config": "reddit_medical"}', true, '{}')
ON CONFLICT (id) DO UPDATE SET
    name = EXCLUDED.name,
    type = EXCLUDED.type,
    base_url = EXCLUDED.base_url,
    config = EXCLUDED.config,
    is_active = EXCLUDED.is_active;

-- Add some common diseases for testing
INSERT INTO diseases (name, synonyms, icd10_codes, mesh_terms) VALUES
('Multiple Sclerosis', '{"MS", "Disseminated Sclerosis"}', '{"G35"}', '{"Multiple Sclerosis", "Sclerosis, Multiple"}'),
('Diabetes', '{"Diabetes Mellitus", "DM"}', '{"E10", "E11", "E13", "E14"}', '{"Diabetes Mellitus", "Diabetes Mellitus, Type 1", "Diabetes Mellitus, Type 2"}'),
('Hypertension', '{"High Blood Pressure", "HTN"}', '{"I10", "I11", "I12", "I13", "I15"}', '{"Hypertension", "Blood Pressure, High"}'),
('Rheumatoid Arthritis', '{"RA", "Atrophic Arthritis"}', '{"M05", "M06"}', '{"Arthritis, Rheumatoid"}'),
('Asthma', '{"Bronchial Asthma"}', '{"J45"}', '{"Asthma"}')
ON CONFLICT (name) DO NOTHING;

-- Reset sequence to ensure future auto-generated IDs don't conflict
SELECT setval('sources_id_seq', (SELECT MAX(id) FROM sources) + 1);
SELECT setval('diseases_id_seq', (SELECT MAX(id) FROM diseases) + 1);