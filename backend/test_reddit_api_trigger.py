#!/usr/bin/env python3
"""Test triggering Reddit scrape via API (without authentication)"""

import asyncio
import httpx
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent))

from core.database import get_pg_connection


async def test_api_trigger():
    """Test triggering a scrape via the regular API"""
    
    print("=== Testing Reddit Scrape via API ===\n")
    
    # Get the source
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
    
    print(f"Source: {source['name']}")
    print(f"Disease: {source['disease_name']} (ID: {source['disease_id']})")
    
    async with httpx.AsyncClient() as client:
        # Trigger via the regular scrapers API
        print("\nTriggering scrape...")
        
        response = await client.post(
            "http://localhost:8000/api/scrapers/trigger",
            json={
                "source_name": "reddit",
                "disease_ids": [source['disease_id']],
                "options": {
                    "source_id": source['id'],
                    "post_limit": 10
                }
            }
        )
        
        print(f"Status: {response.status_code}")
        
        if response.status_code == 200:
            result = response.json()
            print(f"Success! Job ID: {result['job_id']}")
            print(f"Message: {result['message']}")
            
            # Wait a bit for the job to process
            print("\nWaiting 10 seconds for job to process...")
            await asyncio.sleep(10)
            
            # Check job status
            job_response = await client.get(
                f"http://localhost:8000/api/scrapers/jobs/{result['job_id']}"
            )
            
            if job_response.status_code == 200:
                job = job_response.json()
                print(f"\nJob Status: {job['status']}")
                print(f"Documents Found: {job.get('documents_found', 0)}")
                print(f"Documents Processed: {job.get('documents_processed', 0)}")
                print(f"Errors: {job.get('errors', 0)}")
                
                if job.get('error_details'):
                    print(f"Error Details: {json.dumps(job['error_details'], indent=2)}")
            
        else:
            print(f"Failed: {response.text}")


if __name__ == "__main__":
    asyncio.run(test_api_trigger())