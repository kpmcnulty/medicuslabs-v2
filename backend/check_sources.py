#!/usr/bin/env python3
"""Check sources in the database to debug the display issue"""

import asyncio
import asyncpg
import json
from typing import Dict, List

async def check_sources():
    # Connection parameters from the environment
    conn = await asyncpg.connect(
        host='postgres',
        port=5432,
        database='medical_data',
        user='medical_user',
        password='medical_pass'
    )
    
    try:
        # Check all sources
        print("=== ALL SOURCES ===")
        sources = await conn.fetch("""
            SELECT id, name, category, scraper_type, association_method, is_active
            FROM sources
            ORDER BY category, name
        """)
        
        for source in sources:
            status = "✓" if source['is_active'] else "✗"
            print(f"{status} [{source['category']}] {source['name']} (ID: {source['id']}, type: {source['scraper_type']}, method: {source['association_method']})")
        
        print("\n=== COMMUNITY SOURCES ===")
        community_sources = await conn.fetch("""
            SELECT id, name, config
            FROM sources
            WHERE category = 'community' AND is_active = true
            ORDER BY name
        """)
        
        for source in community_sources:
            config = json.loads(source['config']) if source['config'] else {}
            print(f"- {source['name']} (ID: {source['id']})")
            if config:
                print(f"  Config: {json.dumps(config, indent=2)}")
        
        # Check for potential duplicates
        print("\n=== POTENTIAL DUPLICATES ===")
        duplicates = await conn.fetch("""
            SELECT name, COUNT(*) as count
            FROM sources
            GROUP BY name
            HAVING COUNT(*) > 1
        """)
        
        if duplicates:
            for dup in duplicates:
                print(f"- {dup['name']} appears {dup['count']} times")
        else:
            print("No duplicates found")
        
        # Check sources with similar names
        print("\n=== SOURCES WITH SIMILAR NAMES ===")
        similar = await conn.fetch("""
            SELECT s1.name as name1, s2.name as name2
            FROM sources s1, sources s2
            WHERE s1.id < s2.id
            AND (
                s1.name LIKE '%' || s2.name || '%' 
                OR s2.name LIKE '%' || s1.name || '%'
                OR LOWER(REPLACE(s1.name, ' ', '')) = LOWER(REPLACE(s2.name, ' ', ''))
            )
            ORDER BY s1.name, s2.name
        """)
        
        if similar:
            for pair in similar:
                print(f"- '{pair['name1']}' similar to '{pair['name2']}'")
        else:
            print("No similar names found")
            
        # Check what the API would return
        print("\n=== API FILTER RESPONSE ===")
        api_response = await conn.fetch("""
            SELECT s.name, s.category, COUNT(d.id) as doc_count
            FROM sources s
            LEFT JOIN documents d ON s.id = d.source_id
            WHERE s.is_active = true
            GROUP BY s.name, s.category
            ORDER BY s.category, s.name
        """)
        
        categories = {}
        for row in api_response:
            cat = row['category'] or 'uncategorized'
            if cat not in categories:
                categories[cat] = []
            categories[cat].append({
                'name': row['name'],
                'doc_count': row['doc_count']
            })
        
        for cat, sources in categories.items():
            print(f"\n{cat.upper()}:")
            source_names = [s['name'] for s in sources]
            print(f"  Sources: {source_names}")
            print(f"  Concatenated: {''.join(source_names)}")
            
    finally:
        await conn.close()

if __name__ == "__main__":
    asyncio.run(check_sources())