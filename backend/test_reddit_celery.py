#!/usr/bin/env python3
"""Test Reddit scraping through Celery task"""

import asyncio
import sys
import json
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from tasks.scrapers import scrape_reddit
from core.database import get_pg_connection


async def test_celery_scrape():
    """Test Reddit scraping via Celery task"""
    
    print("=== Testing Reddit Scrape via Celery ===\n")
    
    # Get the r/MultipleSclerosis source
    async with get_pg_connection() as conn:
        source = await conn.fetchrow("""
            SELECT s.id, s.name, sd.disease_id, d.name as disease_name
            FROM sources s
            JOIN source_diseases sd ON s.id = sd.source_id
            JOIN diseases d ON sd.disease_id = d.id
            WHERE s.name = 'r/MultipleSclerosis'
        """)
        
        if not source:
            print("ERROR: r/MultipleSclerosis source not found!")
            return
        
        print(f"Source: {source['name']} (ID: {source['id']})")
        print(f"Disease: {source['disease_name']} (ID: {source['disease_id']})")
        
        # Create a job
        job_id = await conn.fetchval("""
            INSERT INTO crawl_jobs (source_id, status, started_at, config)
            VALUES ($1, 'pending', CURRENT_TIMESTAMP, $2)
            RETURNING id
        """, 
            source['id'],
            json.dumps({
                "disease_ids": [source['disease_id']],
                "disease_names": [source['disease_name']],
                "post_limit": 10
            })
        )
        
        print(f"\nCreated job ID: {job_id}")
    
    # Run the task synchronously (not through Celery queue)
    print("\nRunning scraper task...")
    
    result = scrape_reddit(
        disease_ids=[source['disease_id']],
        disease_names=[source['disease_name']],
        job_id=job_id,
        source_id=source['id'],
        source_name=source['name'],
        post_limit=10
    )
    
    print(f"\nResult: {json.dumps(result, indent=2)}")
    
    # Check job status
    async with get_pg_connection() as conn:
        job = await conn.fetchrow("""
            SELECT status, documents_found, documents_processed, errors
            FROM crawl_jobs
            WHERE id = $1
        """, job_id)
        
        print(f"\nJob Status: {job['status']}")
        print(f"Documents Found: {job['documents_found']}")
        print(f"Documents Processed: {job['documents_processed']}")
        print(f"Errors: {job['errors']}")
        
        # Check if documents were saved
        doc_count = await conn.fetchval("""
            SELECT COUNT(*) 
            FROM documents 
            WHERE source_id = $1
            AND scraped_at > CURRENT_TIMESTAMP - INTERVAL '5 minutes'
        """, source['id'])
        
        print(f"\nDocuments saved in last 5 minutes: {doc_count}")


if __name__ == "__main__":
    asyncio.run(test_celery_scrape())