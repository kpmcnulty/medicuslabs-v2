#!/usr/bin/env python3
"""Debug Reddit config issue"""

import asyncio
import sys
import json
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from core.database import get_pg_connection


async def debug_config():
    """Debug config retrieval"""
    
    async with get_pg_connection() as conn:
        # Get source
        source = await conn.fetchrow("""
            SELECT id, name, config, default_config
            FROM sources 
            WHERE name = 'r/MultipleSclerosis'
        """)
        
        print(f"Source: {source['name']}")
        print(f"Config type: {type(source['config'])}")
        print(f"Config value: {source['config']}")
        print(f"Default config type: {type(source['default_config'])}")
        print(f"Default config value: {source['default_config']}")
        
        # Try to access the config
        if isinstance(source['config'], str):
            print("\nConfig is a string, parsing JSON...")
            config = json.loads(source['config'])
        else:
            print("\nConfig is already a dict")
            config = source['config']
            
        print(f"Subreddit: {config.get('subreddit')}")
        
        # Test get_source_config method
        from scrapers.reddit import RedditScraper
        
        async with RedditScraper(source_id=source['id'], source_name=source['name']) as scraper:
            config = await scraper.get_source_config()
            print(f"\nget_source_config returned type: {type(config)}")
            print(f"get_source_config value: {config}")


if __name__ == "__main__":
    asyncio.run(debug_config())