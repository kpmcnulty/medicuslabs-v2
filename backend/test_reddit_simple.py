#!/usr/bin/env python3
"""
Simple test of Reddit scraper

Run this from the API shell:
docker exec -it medical_data_api python test_reddit_simple.py
"""

import asyncio
from scrapers.reddit import RedditScraper
from core.config import settings

async def test_reddit():
    print(f"🔧 Reddit client ID configured: {'Yes' if settings.reddit_client_id else 'No'}")
    print(f"🔧 Reddit client secret configured: {'Yes' if settings.reddit_client_secret else 'No'}")
    
    if not settings.reddit_client_id or not settings.reddit_client_secret:
        print("\n❌ Reddit API credentials not found in environment!")
        print("Please ensure REDDIT_CLIENT_ID and REDDIT_CLIENT_SECRET are set in your .env file")
        return
    
    async with RedditScraper() as scraper:
        # Check if Reddit instance is created
        if not scraper.reddit:
            print("❌ Failed to initialize Reddit API client")
            return
        
        print("✅ Reddit API client initialized successfully!")
        
        # Get config
        config = await scraper.get_source_config()
        print(f"\n📋 Disease-subreddit mappings:")
        disease_subreddits = config.get('disease_subreddits', {})
        for disease, subreddits in disease_subreddits.items():
            print(f"  - {disease}: {', '.join(subreddits)}")
        
        # Test with Multiple Sclerosis
        print("\n🔍 Testing search for Multiple Sclerosis...")
        results = await scraper.search("Multiple Sclerosis", max_results=5)
        
        print(f"\n📊 Found {len(results)} posts")
        if results:
            post = results[0]
            print(f"\nFirst post:")
            print(f"  Title: {post['title'][:80]}...")
            print(f"  Subreddit: r/{post['subreddit']}")
            print(f"  Author: {post['author']}")
            print(f"  Score: {post['score']}")

if __name__ == "__main__":
    asyncio.run(test_reddit())