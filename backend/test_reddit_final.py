#!/usr/bin/env python3
"""
Final test of Reddit scraper with updated metadata

Run from API shell:
docker exec medical_data_api python test_reddit_final.py
"""

import asyncio
from scrapers.reddit import RedditScraper

async def test_new_metadata():
    async with RedditScraper() as scraper:
        print(f"🔍 Testing Reddit scraper with generic metadata fields...")
        print(f"   Source name: {scraper.source_name}")
        
        # Search for Fabry Disease (should find posts in r/FabrysDisease or r/rarediseases)
        results = await scraper.search("Fabry Disease", max_results=3)
        
        if results:
            print(f"\n✅ Found {len(results)} posts")
            post = results[0]
            
            # Extract document data to see metadata structure
            doc, updated_at = scraper.extract_document_data(post)
            
            print(f"\n📋 Metadata structure (generic field names):")
            for key, value in doc.metadata.items():
                if key != 'top_replies':  # Skip long reply data
                    print(f"   {key}: {value}")
            
            print(f"\n📄 Content preview:")
            print(doc.content.split('\n')[0:5])
        else:
            print("\n⚠️  No posts found for Fabry Disease. Trying Multiple Sclerosis...")
            # Try MS instead
            results = await scraper.search("Multiple Sclerosis", max_results=1)
            if results:
                doc, _ = scraper.extract_document_data(results[0])
                print(f"\n📋 Metadata structure:")
                for key, value in doc.metadata.items():
                    if key != 'top_replies':
                        print(f"   {key}: {value}")

if __name__ == "__main__":
    asyncio.run(test_new_metadata())