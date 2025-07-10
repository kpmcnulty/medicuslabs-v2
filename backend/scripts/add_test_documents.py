#!/usr/bin/env python3
"""Add some test documents to the database for better search testing."""

import asyncio
import asyncpg
from datetime import datetime
import json
import os
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://medicuslabs:medicuslabs@localhost:5432/medicuslabs")

test_documents = [
    {
        "source": "PubMed",
        "title": "Novel immunotherapy approaches for metastatic melanoma",
        "content": "Recent advances in checkpoint inhibitor therapy have revolutionized the treatment of metastatic melanoma. This study examines the efficacy of combination PD-1 and CTLA-4 blockade in patients with advanced disease. Results show significant improvement in overall survival rates.",
        "summary": "Study on combination immunotherapy for melanoma showing improved survival outcomes.",
        "url": "https://pubmed.example.com/12345678",
        "metadata": {
            "journal": "Journal of Clinical Oncology",
            "article_types": ["Clinical Trial", "Research Article"],
            "mesh_terms": ["Melanoma", "Immunotherapy", "PD-1", "CTLA-4"],
            "publication_dates": {"pubmed": "2024-03-15"}
        },
        "diseases": ["Melanoma", "Cancer"]
    },
    {
        "source": "ClinicalTrials.gov",
        "title": "Phase 3 Study of Novel SGLT2 Inhibitor in Heart Failure",
        "content": "A randomized, double-blind, placebo-controlled trial evaluating the efficacy and safety of a novel SGLT2 inhibitor in patients with heart failure with preserved ejection fraction (HFpEF). Primary endpoint is cardiovascular death or hospitalization for heart failure.",
        "summary": "Phase 3 trial testing new SGLT2 inhibitor for heart failure treatment.",
        "url": "https://clinicaltrials.gov/study/NCT12345678",
        "metadata": {
            "phase": ["Phase 3"],
            "study_type": "Interventional",
            "status": "Recruiting",
            "start_date": "2024-01-15",
            "conditions": ["Heart Failure", "HFpEF"]
        },
        "diseases": ["Heart Failure", "Cardiovascular Disease"]
    },
    {
        "source": "PubMed",
        "title": "Long COVID neurological manifestations: A systematic review",
        "content": "This systematic review analyzes neurological symptoms in patients with long COVID syndrome. Common manifestations include brain fog, chronic fatigue, headaches, and autonomic dysfunction. The review covers 45 studies with over 10,000 patients.",
        "summary": "Systematic review of neurological symptoms in long COVID patients.",
        "url": "https://pubmed.example.com/87654321",
        "metadata": {
            "journal": "Nature Neurology",
            "article_types": ["Systematic Review", "Meta-Analysis"],
            "mesh_terms": ["COVID-19", "Long COVID", "Neurological Manifestations", "Brain Fog"],
            "publication_dates": {"pubmed": "2024-02-20"}
        },
        "diseases": ["COVID-19", "Long COVID"]
    },
    {
        "source": "PubMed", 
        "title": "Breakthrough in Alzheimer's disease: Tau-targeting antibody shows promise",
        "content": "A phase 2 clinical trial of a novel tau-targeting monoclonal antibody demonstrates significant slowing of cognitive decline in early Alzheimer's disease. The treatment reduced tau pathology as measured by PET imaging and showed favorable safety profile.",
        "summary": "Tau-targeting antibody shows promise in slowing Alzheimer's progression.",
        "url": "https://pubmed.example.com/11223344",
        "metadata": {
            "journal": "The Lancet",
            "article_types": ["Clinical Trial", "Phase 2"],
            "mesh_terms": ["Alzheimer Disease", "Tau Proteins", "Monoclonal Antibodies", "Cognitive Dysfunction"],
            "publication_dates": {"pubmed": "2024-04-01"}
        },
        "diseases": ["Alzheimer's Disease", "Dementia"]
    }
]

async def add_test_documents():
    # Parse PostgreSQL URL
    if DATABASE_URL.startswith("postgresql://"):
        url = DATABASE_URL.replace("postgresql://", "")
        auth, host_db = url.split("@")
        user, password = auth.split(":")
        host_port, database = host_db.split("/")
        if ":" in host_port:
            host, port = host_port.split(":")
            port = int(port)
        else:
            host = host_port
            port = 5432
    else:
        raise ValueError("Invalid DATABASE_URL format")
    
    conn = await asyncpg.connect(
        host=host,
        port=port,
        user=user,
        password=password,
        database=database
    )
    
    try:
        # Get source IDs
        sources = await conn.fetch("SELECT id, name FROM sources")
        source_map = {s['name']: s['id'] for s in sources}
        
        # Get or create diseases
        disease_map = {}
        for doc in test_documents:
            for disease in doc.get('diseases', []):
                if disease not in disease_map:
                    # Check if disease exists
                    existing = await conn.fetchrow(
                        "SELECT id FROM diseases WHERE name = $1",
                        disease
                    )
                    if existing:
                        disease_map[disease] = existing['id']
                    else:
                        # Create new disease
                        new_id = await conn.fetchval(
                            "INSERT INTO diseases (name, created_at) VALUES ($1, $2) RETURNING id",
                            disease, datetime.utcnow()
                        )
                        disease_map[disease] = new_id
                        print(f"Created disease: {disease}")
        
        # Add documents
        for doc in test_documents:
            source_id = source_map.get(doc['source'])
            if not source_id:
                print(f"Source not found: {doc['source']}")
                continue
            
            # Check if document already exists
            existing = await conn.fetchrow(
                "SELECT id FROM documents WHERE url = $1",
                doc['url']
            )
            
            if existing:
                print(f"Document already exists: {doc['title']}")
                continue
            
            # Insert document
            doc_id = await conn.fetchval("""
                INSERT INTO documents (source_id, title, content, summary, url, metadata, created_at, updated_at)
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
                RETURNING id
            """, source_id, doc['title'], doc['content'], doc['summary'], 
                doc['url'], json.dumps(doc['metadata']), datetime.utcnow(), datetime.utcnow())
            
            print(f"Added document: {doc['title']}")
            
            # Link diseases
            for disease in doc.get('diseases', []):
                disease_id = disease_map[disease]
                try:
                    await conn.execute("""
                        INSERT INTO document_diseases (document_id, disease_id, relevance_score, created_at)
                        VALUES ($1, $2, $3, $4)
                        ON CONFLICT DO NOTHING
                    """, doc_id, disease_id, 1.0, datetime.utcnow())
                except Exception as e:
                    print(f"Warning: Could not link disease {disease}: {e}")
        
        # Update search vectors
        print("\nUpdating search vectors...")
        await conn.execute("""
            UPDATE documents 
            SET search_vector = to_tsvector('english', COALESCE(title, '') || ' ' || COALESCE(content, ''))
            WHERE search_vector IS NULL
        """)
        
        # Show final counts
        doc_count = await conn.fetchval("SELECT COUNT(*) FROM documents")
        disease_count = await conn.fetchval("SELECT COUNT(*) FROM diseases")
        print(f"\nDatabase now contains:")
        print(f"- {doc_count} documents")
        print(f"- {disease_count} diseases")
        
    finally:
        await conn.close()

if __name__ == "__main__":
    asyncio.run(add_test_documents())