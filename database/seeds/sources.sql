-- Source seed data for medical data aggregation platform
-- Includes categories and configuration for each source

-- Primary sources (structured data)
INSERT INTO sources (name, type, base_url, category, rate_limit, requires_auth, scraper_type) VALUES
('PubMed', 'primary', 'https://pubmed.ncbi.nlm.nih.gov', 'publications', 10, false, 'pubmed_api'),
('ClinicalTrials.gov', 'primary', 'https://clinicaltrials.gov', 'trials', 10, false, 'clinicaltrials_api');

-- Secondary sources (unstructured data from communities)
INSERT INTO sources (name, type, base_url, category, rate_limit, requires_auth, scraper_type) VALUES
('Reddit Medical', 'secondary', 'https://www.reddit.com', 'community', 60, false, 'reddit_scraper'),
('HealthUnlocked', 'secondary', 'https://healthunlocked.com', 'community', 30, false, 'web_scraper'),
('Patient.info Forums', 'secondary', 'https://patient.info/forums', 'community', 30, false, 'web_scraper');