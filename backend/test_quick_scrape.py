#!/usr/bin/env python3
"""Quick test script to scrape limited data after fixes"""

import asyncio
import sys
import os

from scrapers.clinicaltrials import ClinicalTrialsScraper
from scrapers.reddit import RedditScraper
from scrapers.faers import FAERSScraper
from core.database import get_pg_connection

async def test_clinical_trials():
    """Test clinical trials scraper with limits"""
    print("Testing Clinical Trials scraper...")
    scraper = ClinicalTrialsScraper()
    
    # Test with leukemia, limited results
    results = await scraper.search("leukemia", max_results=5, status="RECRUITING")
    print(f"Found {len(results)} clinical trials")
    
    if results:
        # Process one result to test metadata extraction
        doc, date = scraper.extract_document_data(results[0])
        print(f"Sample metadata fields: {list(doc.metadata.keys())}")
        print(f"Phase: {doc.metadata.get('phase')}")
        print(f"Phases array: {doc.metadata.get('phases')}")
        print(f"Enrollment: {doc.metadata.get('enrollment')}")
        print(f"Start Date: {doc.metadata.get('start_date')}")
        
        # Check raw phases data from API
        if results:
            status = results[0].get("protocolSection", {}).get("statusModule", {})
            print(f"Raw phases from API: {status.get('phases', [])}")
        
        # Save to database
        import json
        async with get_pg_connection() as conn:
            await conn.execute("""
                INSERT INTO documents (source_id, external_id, url, title, content, summary, doc_metadata, scraped_at)
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
                ON CONFLICT (source_id, external_id) DO UPDATE SET
                    title = EXCLUDED.title,
                    content = EXCLUDED.content, 
                    summary = EXCLUDED.summary,
                    doc_metadata = EXCLUDED.doc_metadata,
                    updated_at = NOW()
            """, doc.source_id, doc.external_id, doc.url, doc.title, 
                doc.content, doc.summary, json.dumps(doc.metadata), doc.scraped_at)
        print("Saved to database!")

async def test_reddit():
    """Test Reddit scraper with limits"""
    print("\nTesting Reddit scraper...")
    scraper = RedditScraper(source_id=5, source_name="r/leukemia")
    
    # Test with limited posts and comments
    results = await scraper.search("", subreddit="leukemia", post_limit=3, comment_limit=2)
    print(f"Found {len(results)} Reddit posts")
    
    if results:
        # Process one result to test comment body extraction
        doc, date = scraper.extract_document_data(results[0])
        print(f"Sample metadata fields: {list(doc.metadata.keys())}")
        print(f"Top replies: {len(doc.metadata.get('top_replies', []))}")
        if doc.metadata.get('top_replies'):
            first_reply = doc.metadata['top_replies'][0]
            print(f"First reply has body: {'body' in first_reply}")
            if 'body' in first_reply:
                print(f"Body preview: {first_reply['body'][:50]}...")
        
        # Save to database
        import json
        async with get_pg_connection() as conn:
            await conn.execute("""
                INSERT INTO documents (source_id, external_id, url, title, content, summary, doc_metadata, scraped_at)
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
                ON CONFLICT (source_id, external_id) DO UPDATE SET
                    title = EXCLUDED.title,
                    content = EXCLUDED.content, 
                    summary = EXCLUDED.summary,
                    doc_metadata = EXCLUDED.doc_metadata,
                    updated_at = NOW()
            """, doc.source_id, doc.external_id, doc.url, doc.title, 
                doc.content, doc.summary, json.dumps(doc.metadata), doc.scraped_at)
        print("Reddit post saved to database!")

async def test_faers():
    """Test FAERS scraper with limits"""
    print("\nTesting FAERS scraper...")
    scraper = FAERSScraper(source_id=18, source_name="FDA FAERS")
    
    # Test with limited results
    results = await scraper.search("leukemia", max_results=3)
    print(f"Found {len(results)} FAERS reports")
    
    if results:
        # Process one result to test metadata extraction
        doc, date = scraper.extract_document_data(results[0])
        print(f"Sample metadata fields: {list(doc.metadata.keys())}")
        print(f"Drugs: {doc.metadata.get('drugs', [])[:2] if doc.metadata.get('drugs') else 'None'}")
        print(f"Reactions: {doc.metadata.get('reactions', [])[:2] if doc.metadata.get('reactions') else 'None'}")
        print(f"Report Type: {doc.metadata.get('report_type')}")
        
        # Save to database
        import json
        async with get_pg_connection() as conn:
            await conn.execute("""
                INSERT INTO documents (source_id, external_id, url, title, content, summary, doc_metadata, scraped_at)
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
                ON CONFLICT (source_id, external_id) DO UPDATE SET
                    title = EXCLUDED.title,
                    content = EXCLUDED.content, 
                    summary = EXCLUDED.summary,
                    doc_metadata = EXCLUDED.doc_metadata,
                    updated_at = NOW()
            """, doc.source_id, doc.external_id, doc.url, doc.title, 
                doc.content, doc.summary, json.dumps(doc.metadata), doc.scraped_at)
        print("FAERS report saved to database!")

if __name__ == "__main__":
    async def main():
        await test_clinical_trials()
        await test_reddit()
        await test_faers()
    
    asyncio.run(main())