-- Simple source seed data for medical data aggregation platform
-- This replaces the overcomplicated YAML configuration with straightforward SQL

-- Primary sources (structured data)
INSERT INTO sources (name, type, base_url, description) VALUES
('ClinicalTrials.gov', 'primary', 'https://clinicaltrials.gov', 'Official registry of clinical research studies'),
('PubMed', 'primary', 'https://pubmed.ncbi.nlm.nih.gov', 'Peer-reviewed medical literature database'),
('Cochrane Library', 'primary', 'https://www.cochranelibrary.com', 'Systematic reviews and evidence synthesis'),
('FDA FAERS', 'primary', 'https://www.fda.gov/drugs/surveillance/faers', 'Adverse event reporting system');

-- Secondary sources (unstructured data)
INSERT INTO sources (name, type, base_url, description) VALUES
('HealthUnlocked', 'secondary', 'https://healthunlocked.com', 'Patient community and support forums'),
('Patient.info Forums', 'secondary', 'https://patient.info/forums', 'Medical Q&A and patient discussions'),
('PatientsLikeMe', 'secondary', 'https://www.patientslikeme.com', 'Patient experience and treatment tracking'),
('Reddit Medical', 'secondary', 'https://www.reddit.com/r/medical', 'Medical discussion communities'),
('Medical Blogs', 'secondary', 'https://various-medical-blogs.com', 'Healthcare professional and patient blogs');