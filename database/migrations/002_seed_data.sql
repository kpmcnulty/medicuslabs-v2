-- Seed data for medical data platform
-- Based on files in database/seeds/ directory

-- Sources
INSERT INTO sources (name, category, base_url, scraper_type, rate_limit) VALUES
-- Publications
('PubMed', 'publications', 'https://pubmed.ncbi.nlm.nih.gov', 'pubmed_api', 10),

-- Clinical Trials
('ClinicalTrials.gov', 'trials', 'https://clinicaltrials.gov', 'clinicaltrials_api', 10),

-- Community Forums
('Reddit Medical', 'community', 'https://www.reddit.com', 'reddit_scraper', 60),
('HealthUnlocked', 'community', 'https://healthunlocked.com', 'web_scraper', 30),
('Patient.info Forums', 'community', 'https://patient.info/forums', 'web_scraper', 30)
ON CONFLICT (name) DO NOTHING;

-- Diseases (user-specified diseases for targeted medical research)
INSERT INTO diseases (name, synonyms) VALUES
('Multiple Sclerosis', '{"MS", "Disseminated sclerosis", "Encephalomyelitis disseminata"}'),
('Alpha-1 Antitrypsin Deficiency', '{"AATD", "Alpha-1", "A1AT deficiency", "AAT deficiency"}'),
('Fabry Disease', '{"Fabry", "Anderson-Fabry disease", "Alpha-galactosidase A deficiency"}'),
('Systemic Scleroderma', '{"Systemic sclerosis", "SSc", "Scleroderma", "Diffuse scleroderma"}'),
('Phenylketonuria', '{"PKU", "Phenylalanine hydroxylase deficiency", "Folling disease"}'),
('Amyotrophic Lateral Sclerosis', '{"ALS", "Lou Gehrig disease", "Motor neuron disease", "MND"}'),
('Acute Myeloid Leukemia', '{"AML", "Acute myelogenous leukemia", "Acute nonlymphocytic leukemia"}')
ON CONFLICT (name) DO NOTHING;