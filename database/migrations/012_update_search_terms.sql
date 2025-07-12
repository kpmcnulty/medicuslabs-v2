-- Update search terms for all diseases

UPDATE diseases SET search_terms = 
  ARRAY['multiple sclerosis', 'MS', 'RRMS', 'PPMS', 'SPMS', 'relapsing remitting', 'primary progressive', 'secondary progressive']
WHERE name = 'Multiple Sclerosis';

UPDATE diseases SET search_terms = 
  ARRAY['alpha-1 antitrypsin deficiency', 'AATD', 'alpha-1', 'A1AT deficiency', 'AAT deficiency', 'alpha 1 antitrypsin']
WHERE name = 'Alpha-1 Antitrypsin Deficiency';

UPDATE diseases SET search_terms = 
  ARRAY['fabry disease', 'fabry', 'anderson-fabry disease', 'alpha-galactosidase A deficiency', 'fabrys disease']
WHERE name = 'Fabry Disease';

UPDATE diseases SET search_terms = 
  ARRAY['systemic scleroderma', 'systemic sclerosis', 'SSc', 'scleroderma', 'diffuse scleroderma', 'limited scleroderma']
WHERE name = 'Systemic Scleroderma';

UPDATE diseases SET search_terms = 
  ARRAY['phenylketonuria', 'PKU', 'phenylalanine hydroxylase deficiency', 'folling disease', 'hyperphenylalaninemia']
WHERE name = 'Phenylketonuria';

UPDATE diseases SET search_terms = 
  ARRAY['ALS', 'amyotrophic lateral sclerosis', 'lou gehrig disease', 'lou gehrigs disease', 'motor neuron disease', 'MND', 'motor neurone disease']
WHERE name = 'Amyotrophic Lateral Sclerosis';

UPDATE diseases SET search_terms = 
  ARRAY['AML', 'acute myeloid leukemia', 'acute myelogenous leukemia', 'acute nonlymphocytic leukemia', 'acute myeloblastic leukemia']
WHERE name = 'Acute Myeloid Leukemia';

-- Verify the update
SELECT name, array_length(search_terms, 1) as term_count 
FROM diseases 
ORDER BY name;