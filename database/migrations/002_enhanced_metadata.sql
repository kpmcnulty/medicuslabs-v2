-- Enhanced metadata schema for comprehensive data capture
-- Run this after the base schema is set up

-- Add new tables for enhanced metadata relationships

-- Authors table for detailed author information
CREATE TABLE IF NOT EXISTS authors (
    id SERIAL PRIMARY KEY,
    name TEXT NOT NULL,
    orcid TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(name, orcid)
);

-- Author affiliations
CREATE TABLE IF NOT EXISTS author_affiliations (
    id SERIAL PRIMARY KEY,
    author_id INTEGER REFERENCES authors(id) ON DELETE CASCADE,
    institution TEXT NOT NULL,
    department TEXT,
    country TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Document authors relationship
CREATE TABLE IF NOT EXISTS document_authors (
    id SERIAL PRIMARY KEY,
    document_id INTEGER REFERENCES documents(id) ON DELETE CASCADE,
    author_id INTEGER REFERENCES authors(id) ON DELETE CASCADE,
    position INTEGER, -- Author order
    is_corresponding BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(document_id, author_id)
);

-- Grants and funding information
CREATE TABLE IF NOT EXISTS grants (
    id SERIAL PRIMARY KEY,
    grant_id TEXT NOT NULL,
    agency TEXT,
    country TEXT,
    title TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(grant_id, agency)
);

-- Document grants relationship
CREATE TABLE IF NOT EXISTS document_grants (
    id SERIAL PRIMARY KEY,
    document_id INTEGER REFERENCES documents(id) ON DELETE CASCADE,
    grant_id INTEGER REFERENCES grants(id) ON DELETE CASCADE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(document_id, grant_id)
);

-- Chemical substances
CREATE TABLE IF NOT EXISTS chemicals (
    id SERIAL PRIMARY KEY,
    name TEXT NOT NULL UNIQUE,
    registry_number TEXT,
    mesh_id TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Document chemicals relationship
CREATE TABLE IF NOT EXISTS document_chemicals (
    id SERIAL PRIMARY KEY,
    document_id INTEGER REFERENCES documents(id) ON DELETE CASCADE,
    chemical_id INTEGER REFERENCES chemicals(id) ON DELETE CASCADE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(document_id, chemical_id)
);

-- References/Citations
CREATE TABLE IF NOT EXISTS references (
    id SERIAL PRIMARY KEY,
    citation_text TEXT NOT NULL,
    pmid TEXT,
    doi TEXT,
    title TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Document references relationship
CREATE TABLE IF NOT EXISTS document_references (
    id SERIAL PRIMARY KEY,
    document_id INTEGER REFERENCES documents(id) ON DELETE CASCADE,
    reference_id INTEGER REFERENCES references(id) ON DELETE CASCADE,
    reference_type TEXT, -- 'cited_by', 'cites', 'correction', etc.
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(document_id, reference_id, reference_type)
);

-- Clinical trial specific tables

-- Principal Investigators
CREATE TABLE IF NOT EXISTS investigators (
    id SERIAL PRIMARY KEY,
    name TEXT NOT NULL,
    role TEXT, -- 'Principal Investigator', 'Sub-Investigator', etc.
    affiliation TEXT,
    email TEXT,
    phone TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Document investigators relationship (for clinical trials)
CREATE TABLE IF NOT EXISTS document_investigators (
    id SERIAL PRIMARY KEY,
    document_id INTEGER REFERENCES documents(id) ON DELETE CASCADE,
    investigator_id INTEGER REFERENCES investigators(id) ON DELETE CASCADE,
    site_location TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(document_id, investigator_id)
);

-- Study documents (protocols, statistical plans, etc.)
CREATE TABLE IF NOT EXISTS study_documents (
    id SERIAL PRIMARY KEY,
    document_id INTEGER REFERENCES documents(id) ON DELETE CASCADE,
    doc_type TEXT NOT NULL, -- 'protocol', 'statistical_analysis_plan', 'informed_consent'
    title TEXT,
    url TEXT,
    file_size INTEGER,
    upload_date DATE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Add indexes for performance
CREATE INDEX IF NOT EXISTS idx_authors_name ON authors(name);
CREATE INDEX IF NOT EXISTS idx_authors_orcid ON authors(orcid);
CREATE INDEX IF NOT EXISTS idx_document_authors_document_id ON document_authors(document_id);
CREATE INDEX IF NOT EXISTS idx_document_grants_document_id ON document_grants(document_id);
CREATE INDEX IF NOT EXISTS idx_document_chemicals_document_id ON document_chemicals(document_id);
CREATE INDEX IF NOT EXISTS idx_document_references_document_id ON document_references(document_id);
CREATE INDEX IF NOT EXISTS idx_chemicals_name ON chemicals(name);
CREATE INDEX IF NOT EXISTS idx_grants_grant_id ON grants(grant_id);
CREATE INDEX IF NOT EXISTS idx_references_pmid ON references(pmid);
CREATE INDEX IF NOT EXISTS idx_references_doi ON references(doi);

-- Add full text search indexes
CREATE INDEX IF NOT EXISTS idx_authors_name_fts ON authors USING gin(to_tsvector('english', name));
CREATE INDEX IF NOT EXISTS idx_chemicals_name_fts ON chemicals USING gin(to_tsvector('english', name));
CREATE INDEX IF NOT EXISTS idx_references_citation_fts ON references USING gin(to_tsvector('english', citation_text));

-- Add comments for documentation
COMMENT ON TABLE authors IS 'Detailed author information with ORCID IDs';
COMMENT ON TABLE author_affiliations IS 'Author institutional affiliations';
COMMENT ON TABLE grants IS 'Research grants and funding information';
COMMENT ON TABLE chemicals IS 'Chemical substances mentioned in publications';
COMMENT ON TABLE references IS 'Citations and references between documents';
COMMENT ON TABLE investigators IS 'Principal investigators for clinical trials';
COMMENT ON TABLE study_documents IS 'Associated documents for clinical studies';

-- Update the documents table to add new metadata fields
ALTER TABLE documents ADD COLUMN IF NOT EXISTS pmc_id TEXT;
ALTER TABLE documents ADD COLUMN IF NOT EXISTS issn TEXT;
ALTER TABLE documents ADD COLUMN IF NOT EXISTS impact_factor FLOAT;
ALTER TABLE documents ADD COLUMN IF NOT EXISTS publication_types TEXT[];
ALTER TABLE documents ADD COLUMN IF NOT EXISTS mesh_major TEXT[]; -- Major MeSH terms
ALTER TABLE documents ADD COLUMN IF NOT EXISTS mesh_minor TEXT[]; -- Minor MeSH terms
ALTER TABLE documents ADD COLUMN IF NOT EXISTS received_date DATE;
ALTER TABLE documents ADD COLUMN IF NOT EXISTS accepted_date DATE;
ALTER TABLE documents ADD COLUMN IF NOT EXISTS revised_date DATE;
ALTER TABLE documents ADD COLUMN IF NOT EXISTS epub_date DATE;

-- Clinical trials specific fields
ALTER TABLE documents ADD COLUMN IF NOT EXISTS trial_phase TEXT[];
ALTER TABLE documents ADD COLUMN IF NOT EXISTS study_design TEXT;
ALTER TABLE documents ADD COLUMN IF NOT EXISTS primary_purpose TEXT;
ALTER TABLE documents ADD COLUMN IF NOT EXISTS masking TEXT;
ALTER TABLE documents ADD COLUMN IF NOT EXISTS allocation TEXT;
ALTER TABLE documents ADD COLUMN IF NOT EXISTS intervention_model TEXT;
ALTER TABLE documents ADD COLUMN IF NOT EXISTS target_duration TEXT;
ALTER TABLE documents ADD COLUMN IF NOT EXISTS biospec_retention TEXT;
ALTER TABLE documents ADD COLUMN IF NOT EXISTS biospec_description TEXT;

-- Add indexes for new fields
CREATE INDEX IF NOT EXISTS idx_documents_pmc_id ON documents(pmc_id);
CREATE INDEX IF NOT EXISTS idx_documents_received_date ON documents(received_date);
CREATE INDEX IF NOT EXISTS idx_documents_trial_phase ON documents USING gin(trial_phase);
CREATE INDEX IF NOT EXISTS idx_documents_study_design ON documents(study_design);

-- Create views for easier querying

-- Author publication count view
CREATE OR REPLACE VIEW author_publication_stats AS
SELECT 
    a.id,
    a.name,
    a.orcid,
    COUNT(da.document_id) as publication_count,
    MIN(d.created_at) as first_publication,
    MAX(d.created_at) as latest_publication
FROM authors a
LEFT JOIN document_authors da ON a.id = da.author_id
LEFT JOIN documents d ON da.document_id = d.id
GROUP BY a.id, a.name, a.orcid;

-- Grant funding summary view
CREATE OR REPLACE VIEW grant_funding_stats AS
SELECT 
    g.agency,
    g.country,
    COUNT(dg.document_id) as funded_documents,
    COUNT(DISTINCT g.grant_id) as total_grants
FROM grants g
LEFT JOIN document_grants dg ON g.id = dg.grant_id
GROUP BY g.agency, g.country;

-- Chemical research trends view
CREATE OR REPLACE VIEW chemical_research_trends AS
SELECT 
    c.name as chemical_name,
    COUNT(dc.document_id) as document_count,
    COUNT(DISTINCT EXTRACT(YEAR FROM d.created_at)) as years_studied
FROM chemicals c
LEFT JOIN document_chemicals dc ON c.id = dc.chemical_id
LEFT JOIN documents d ON dc.document_id = d.id
GROUP BY c.id, c.name
ORDER BY document_count DESC;

COMMENT ON VIEW author_publication_stats IS 'Author productivity statistics';
COMMENT ON VIEW grant_funding_stats IS 'Funding agency statistics';
COMMENT ON VIEW chemical_research_trends IS 'Chemical substance research trends';