-- Migration to add association_method and source_diseases junction table
-- This enables both search-based sources (PubMed) and fixed sources (r/MultipleSclerosis)

-- Add association_method to sources
ALTER TABLE sources ADD COLUMN association_method VARCHAR(20) DEFAULT 'search';

-- Add constraint to ensure valid values
ALTER TABLE sources ADD CONSTRAINT check_association_method 
CHECK (association_method IN ('search', 'fixed'));

-- Create junction table for fixed sources to specify their diseases
CREATE TABLE source_diseases (
    source_id INTEGER NOT NULL REFERENCES sources(id) ON DELETE CASCADE,
    disease_id INTEGER NOT NULL REFERENCES diseases(id) ON DELETE CASCADE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (source_id, disease_id)
);

-- Add index for performance
CREATE INDEX idx_source_diseases_source_id ON source_diseases(source_id);
CREATE INDEX idx_source_diseases_disease_id ON source_diseases(disease_id);

-- Update existing sources to use appropriate association methods
UPDATE sources SET association_method = 'search' WHERE name IN ('PubMed', 'ClinicalTrials.gov');
UPDATE sources SET association_method = 'fixed' WHERE category = 'community';

-- Remove the disease_id column from previous migration (if it exists)
-- We're using the junction table instead for more flexibility
ALTER TABLE sources DROP COLUMN IF EXISTS disease_id;

-- Add comments
COMMENT ON COLUMN sources.association_method IS 'How documents from this source are associated with diseases: "search" = by search term, "fixed" = pre-linked to specific diseases';
COMMENT ON TABLE source_diseases IS 'Links fixed sources to their specific diseases. Only used when association_method = "fixed"';
COMMENT ON COLUMN source_diseases.source_id IS 'The source that covers specific diseases';
COMMENT ON COLUMN source_diseases.disease_id IS 'A disease that this source covers';