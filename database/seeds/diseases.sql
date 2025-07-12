-- Core diseases for medical data aggregation platform
-- These 7 diseases are the focus of our data collection

INSERT INTO diseases (name, synonyms, search_terms) VALUES
('Multiple Sclerosis', 
  '{"MS", "Disseminated sclerosis", "Encephalomyelitis disseminata"}',
  '{"multiple sclerosis", "MS", "RRMS", "PPMS", "SPMS", "relapsing remitting", "primary progressive", "secondary progressive"}'),

('Alpha-1 Antitrypsin Deficiency', 
  '{"AATD", "Alpha-1", "A1AT deficiency", "AAT deficiency"}',
  '{"alpha-1 antitrypsin deficiency", "AATD", "alpha-1", "A1AT deficiency", "AAT deficiency", "alpha 1 antitrypsin"}'),

('Fabry Disease', 
  '{"Fabry", "Anderson-Fabry disease", "Alpha-galactosidase A deficiency"}',
  '{"fabry disease", "fabry", "anderson-fabry disease", "alpha-galactosidase A deficiency", "fabrys disease"}'),

('Systemic Scleroderma', 
  '{"Systemic sclerosis", "SSc", "Scleroderma", "Diffuse scleroderma"}',
  '{"systemic scleroderma", "systemic sclerosis", "SSc", "scleroderma", "diffuse scleroderma", "limited scleroderma"}'),

('Phenylketonuria', 
  '{"PKU", "Phenylalanine hydroxylase deficiency", "Folling disease"}',
  '{"phenylketonuria", "PKU", "phenylalanine hydroxylase deficiency", "folling disease", "hyperphenylalaninemia"}'),

('Amyotrophic Lateral Sclerosis', 
  '{"ALS", "Lou Gehrig disease", "Motor neuron disease", "MND"}',
  '{"ALS", "amyotrophic lateral sclerosis", "lou gehrig disease", "lou gehrigs disease", "motor neuron disease", "MND", "motor neurone disease"}'),

('Acute Myeloid Leukemia', 
  '{"AML", "Acute myelogenous leukemia", "Acute nonlymphocytic leukemia"}',
  '{"AML", "acute myeloid leukemia", "acute myelogenous leukemia", "acute nonlymphocytic leukemia", "acute myeloblastic leukemia"}')

ON CONFLICT (name) DO UPDATE SET 
  synonyms = EXCLUDED.synonyms,
  search_terms = EXCLUDED.search_terms;