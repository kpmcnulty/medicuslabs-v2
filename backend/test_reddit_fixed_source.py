#!/usr/bin/env python3
"""
Test script for Reddit fixed source scraping
Tests the updated Reddit scraper with the new source association system
"""

import asyncio
import sys
from datetime import datetime
import json
from pathlib import Path

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent))

from scrapers.reddit import RedditScraper
from core.database import get_pg_connection
from core.config import settings


async def test_reddit_fixed_source():
    """Test Reddit scraping for a fixed source (subreddit)"""
    
    print("=== Reddit Fixed Source Test ===\n")
    
    # Get the r/MultipleSclerosis source
    async with get_pg_connection() as conn:
        source = await conn.fetchrow("""
            SELECT id, name, config, association_method
            FROM sources 
            WHERE name = 'r/MultipleSclerosis'
        """)
        
        if not source:
            print("ERROR: r/MultipleSclerosis source not found!")
            return
        
        print(f"Source: {source['name']}")
        print(f"ID: {source['id']}")
        print(f"Association Method: {source['association_method']}")
        print(f"Config: {json.dumps(source['config'], indent=2)}")
        
        # Get linked diseases
        diseases = await conn.fetch("""
            SELECT d.id, d.name
            FROM diseases d
            JOIN source_diseases sd ON d.id = sd.disease_id
            WHERE sd.source_id = $1
        """, source['id'])
        
        print(f"\nLinked Diseases:")
        for disease in diseases:
            print(f"  - {disease['name']} (ID: {disease['id']})")
    
    # Check Reddit credentials
    print(f"\nReddit Credentials:")
    print(f"  Client ID: {'✓' if settings.reddit_client_id else '✗ Missing'}")
    print(f"  Client Secret: {'✓' if settings.reddit_client_secret else '✗ Missing'}")
    print(f"  User Agent: {settings.reddit_user_agent}")
    
    if not settings.reddit_client_id or not settings.reddit_client_secret:
        print("\nERROR: Reddit API credentials not configured in .env file!")
        print("Please add REDDIT_CLIENT_ID and REDDIT_CLIENT_SECRET to your .env file")
        return
    
    # Test the scraper
    print(f"\n--- Testing Reddit Scraper ---")
    
    try:
        async with RedditScraper(
            source_id=source['id'], 
            source_name=source['name']
        ) as scraper:
            
            # Test search (for fixed sources, disease_term is ignored)
            print(f"\nSearching subreddit (first 5 posts)...")
            results = await scraper.search("", max_results=5)
            
            print(f"Found {len(results)} posts")
            
            for i, post in enumerate(results[:3], 1):
                print(f"\n{i}. {post['title']}")
                print(f"   Author: {post['author']}")
                print(f"   Score: {post['score']}")
                print(f"   Comments: {post['num_comments']}")
                print(f"   URL: {post['url']}")
                
                if post.get('comments'):
                    print(f"   Top comment: {post['comments'][0]['body'][:100]}...")
            
            # Test document extraction
            if results:
                print(f"\n--- Testing Document Extraction ---")
                doc, updated_at = scraper.extract_document_data(results[0])
                
                print(f"Document ID: {doc.external_id}")
                print(f"Title: {doc.title}")
                print(f"Summary: {doc.summary[:200]}...")
                print(f"Metadata keys: {list(doc.metadata.keys())}")
                print(f"Source Updated At: {updated_at}")
                
    except Exception as e:
        print(f"\nERROR during scraping: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()


async def test_trigger_scrape_api():
    """Test triggering a scrape via the admin API"""
    
    print("\n\n=== Testing Admin API Trigger ===\n")
    
    try:
        import httpx
        
        # Login first
        async with httpx.AsyncClient() as client:
            # Get admin credentials
            admin_user = settings.admin_username or 'admin'
            admin_pass = 'admin123'  # Default password, should be changed
            
            print(f"Logging in as {admin_user}...")
            
            login_response = await client.post(
                "http://localhost:8000/api/admin/auth/login",
                json={"username": admin_user, "password": admin_pass}
            )
            
            if login_response.status_code != 200:
                print(f"Login failed: {login_response.status_code}")
                print(f"Response: {login_response.text}")
                return
            
            token = login_response.json()["access_token"]
            print("Login successful!")
            
            # Trigger scrape for r/MultipleSclerosis
            headers = {"Authorization": f"Bearer {token}"}
            
            async with get_pg_connection() as conn:
                source = await conn.fetchrow(
                    "SELECT id FROM sources WHERE name = 'r/MultipleSclerosis'"
                )
                
                if not source:
                    print("Source not found!")
                    return
            
            print(f"\nTriggering scrape for source ID {source['id']}...")
            
            trigger_response = await client.post(
                f"http://localhost:8000/api/admin/sources/{source['id']}/trigger-scrape",
                headers=headers,
                json={
                    "options": {
                        "post_limit": 10,
                        "include_comments": True,
                        "comment_limit": 5
                    }
                }
            )
            
            if trigger_response.status_code == 200:
                result = trigger_response.json()
                print(f"Success! Job ID: {result['job_id']}")
                print(f"Message: {result['message']}")
                print(f"Details: {json.dumps(result['details'], indent=2)}")
            else:
                print(f"Failed: {trigger_response.status_code}")
                print(f"Response: {trigger_response.text}")
                
    except Exception as e:
        print(f"\nERROR: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()


async def main():
    """Run all tests"""
    
    # Test direct scraping
    await test_reddit_fixed_source()
    
    # Test API trigger
    await test_trigger_scrape_api()
    
    print("\n\n=== Test Complete ===")


if __name__ == "__main__":
    asyncio.run(main())