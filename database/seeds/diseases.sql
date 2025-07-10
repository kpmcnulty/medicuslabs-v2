-- Simple disease seed data for medical data aggregation platform
-- User-specified diseases for targeted medical research

INSERT INTO diseases (name, synonyms) VALUES
('Multiple Sclerosis', '{"MS", "Disseminated sclerosis", "Encephalomyelitis disseminata"}'),
('Alpha-1 Antitrypsin Deficiency', '{"AATD", "Alpha-1", "A1AT deficiency", "AAT deficiency"}'),
('Fabry Disease', '{"Fabry", "Anderson-Fabry disease", "Alpha-galactosidase A deficiency"}'),
('Systemic Scleroderma', '{"Systemic sclerosis", "SSc", "Scleroderma", "Diffuse scleroderma"}'),
('Phenylketonuria', '{"PKU", "Phenylalanine hydroxylase deficiency", "Folling disease"}'),
('Amyotrophic Lateral Sclerosis', '{"ALS", "Lou Gehrig disease", "Motor neuron disease", "MND"}'),
('Acute Myeloid Leukemia', '{"AML", "Acute myelogenous leukemia", "Acute nonlymphocytic leukemia"}');