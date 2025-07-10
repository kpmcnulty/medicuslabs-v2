-- Enable required extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pgcrypto";
CREATE EXTENSION IF NOT EXISTS "vector";

-- Create enum types
CREATE TYPE source_type AS ENUM ('primary', 'secondary');
CREATE TYPE document_status AS ENUM ('pending', 'processing', 'processed', 'failed');

-- Core tables
CREATE TABLE sources (
    id SERIAL PRIMARY KEY,
    name TEXT NOT NULL UNIQUE,
    type source_type NOT NULL,
    base_url TEXT,
    config JSONB DEFAULT '{}',
    is_active BOOLEAN DEFAULT true,
    last_crawled TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Documents table with partitioning support
CREATE TABLE documents (
    id SERIAL,
    source_id INTEGER REFERENCES sources(id) ON DELETE CASCADE,
    external_id TEXT,
    url TEXT,
    title TEXT,
    content TEXT,
    summary TEXT,
    raw_path TEXT,
    status document_status DEFAULT 'pending',
    language VARCHAR(10) DEFAULT 'en',
    relevance_score FLOAT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    scraped_at TIMESTAMP,
    embedding vector(384),
    metadata JSONB DEFAULT '{}',
    PRIMARY KEY (id, created_at)
) PARTITION BY RANGE (created_at);

-- Create partitions for the next 12 months
DO $$
DECLARE
    start_date date;
    end_date date;
    partition_name text;
BEGIN
    FOR i IN 0..11 LOOP
        start_date := DATE_TRUNC('month', CURRENT_DATE + (i || ' months')::interval);
        end_date := DATE_TRUNC('month', start_date + '1 month'::interval);
        partition_name := 'documents_' || TO_CHAR(start_date, 'YYYY_MM');
        
        EXECUTE format('
            CREATE TABLE IF NOT EXISTS %I PARTITION OF documents
            FOR VALUES FROM (%L) TO (%L);',
            partition_name, start_date, end_date
        );
    END LOOP;
END $$;

-- Diseases table
CREATE TABLE diseases (
    id SERIAL PRIMARY KEY,
    name TEXT NOT NULL UNIQUE,
    description TEXT,
    synonyms TEXT[] DEFAULT '{}',
    icd10_codes TEXT[] DEFAULT '{}',
    mesh_terms TEXT[] DEFAULT '{}',
    snomed_codes TEXT[] DEFAULT '{}',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Document-Disease relationships
CREATE TABLE document_diseases (
    id SERIAL PRIMARY KEY,
    document_id INTEGER NOT NULL,
    disease_id INTEGER REFERENCES diseases(id) ON DELETE CASCADE,
    relevance_score FLOAT DEFAULT 0.0,
    confidence FLOAT DEFAULT 0.0,
    extracted_terms TEXT[],
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (document_id, created_at) REFERENCES documents(id, created_at) ON DELETE CASCADE
);

-- Crawl jobs table
CREATE TABLE crawl_jobs (
    id SERIAL PRIMARY KEY,
    source_id INTEGER REFERENCES sources(id) ON DELETE CASCADE,
    status VARCHAR(50) DEFAULT 'pending',
    started_at TIMESTAMP,
    completed_at TIMESTAMP,
    documents_found INTEGER DEFAULT 0,
    documents_processed INTEGER DEFAULT 0,
    errors INTEGER DEFAULT 0,
    error_details JSONB DEFAULT '[]',
    config JSONB DEFAULT '{}',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Search queries table for analytics
CREATE TABLE search_queries (
    id SERIAL PRIMARY KEY,
    query_text TEXT NOT NULL,
    query_vector vector(384),
    filters JSONB DEFAULT '{}',
    results_count INTEGER DEFAULT 0,
    user_id TEXT,
    session_id TEXT,
    execution_time_ms INTEGER,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- User saved searches
CREATE TABLE saved_searches (
    id SERIAL PRIMARY KEY,
    user_id TEXT NOT NULL,
    name TEXT NOT NULL,
    query_text TEXT,
    filters JSONB DEFAULT '{}',
    alert_enabled BOOLEAN DEFAULT false,
    alert_frequency VARCHAR(50) DEFAULT 'daily',
    last_alerted_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Create indexes for better performance
CREATE INDEX idx_documents_source_id ON documents(source_id);
CREATE INDEX idx_documents_external_id ON documents(external_id);
CREATE INDEX idx_documents_status ON documents(status);
CREATE INDEX idx_documents_created_at ON documents(created_at);
CREATE INDEX idx_documents_embedding ON documents USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100);
CREATE INDEX idx_documents_metadata ON documents USING GIN (metadata);
CREATE INDEX idx_documents_content_fts ON documents USING GIN (to_tsvector('english', content));
CREATE INDEX idx_documents_title_fts ON documents USING GIN (to_tsvector('english', title));

CREATE INDEX idx_document_diseases_document_id ON document_diseases(document_id);
CREATE INDEX idx_document_diseases_disease_id ON document_diseases(disease_id);
CREATE INDEX idx_document_diseases_relevance ON document_diseases(relevance_score);

CREATE INDEX idx_diseases_name ON diseases(name);
CREATE INDEX idx_diseases_synonyms ON diseases USING GIN (synonyms);
CREATE INDEX idx_diseases_mesh_terms ON diseases USING GIN (mesh_terms);

CREATE INDEX idx_crawl_jobs_source_id ON crawl_jobs(source_id);
CREATE INDEX idx_crawl_jobs_status ON crawl_jobs(status);
CREATE INDEX idx_crawl_jobs_created_at ON crawl_jobs(created_at);

-- Create update timestamp trigger
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ language 'plpgsql';

CREATE TRIGGER update_sources_updated_at BEFORE UPDATE ON sources
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_documents_updated_at BEFORE UPDATE ON documents
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_diseases_updated_at BEFORE UPDATE ON diseases
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_saved_searches_updated_at BEFORE UPDATE ON saved_searches
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- Create views for common queries
CREATE VIEW recent_documents AS
SELECT 
    d.*,
    s.name as source_name,
    s.type as source_type
FROM documents d
JOIN sources s ON d.source_id = s.id
WHERE d.created_at > CURRENT_TIMESTAMP - INTERVAL '7 days'
ORDER BY d.created_at DESC;

CREATE VIEW document_disease_summary AS
SELECT 
    d.id,
    d.title,
    d.source_id,
    COUNT(dd.disease_id) as disease_count,
    ARRAY_AGG(dis.name) as disease_names,
    AVG(dd.relevance_score) as avg_relevance
FROM documents d
LEFT JOIN document_diseases dd ON d.id = dd.document_id
LEFT JOIN diseases dis ON dd.disease_id = dis.id
GROUP BY d.id, d.title, d.source_id;

-- Insert initial data
INSERT INTO sources (name, type, base_url, config) VALUES
    ('ClinicalTrials.gov', 'primary', 'https://clinicaltrials.gov/api/v2/', '{"rate_limit": 10, "timeout": 30}'),
    ('PubMed', 'primary', 'https://eutils.ncbi.nlm.nih.gov/entrez/eutils/', '{"rate_limit": 3, "timeout": 30, "api_key": null}'),
    ('Reddit Medical', 'secondary', 'https://www.reddit.com/r/medical/', '{"rate_limit": 1, "timeout": 30}'),
    ('HealthUnlocked', 'secondary', 'https://healthunlocked.com/', '{"rate_limit": 1, "timeout": 30}'),
    ('Patient.info Forums', 'secondary', 'https://patient.info/forums', '{"rate_limit": 1, "timeout": 30}');

-- Grant permissions
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO medical_user;
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO medical_user;
GRANT ALL PRIVILEGES ON ALL FUNCTIONS IN SCHEMA public TO medical_user;