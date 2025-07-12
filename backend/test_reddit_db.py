#!/usr/bin/env python3
"""
Test Reddit documents in database

Run from API shell:
docker exec medical_data_api python test_reddit_db.py
"""

import asyncio
from core.database import get_pg_connection

async def test_reddit_docs():
    async with get_pg_connection() as conn:
        # Get Reddit documents
        result = await conn.fetch("""
            SELECT d.id, d.title, d.external_id, d.doc_metadata->>'subreddit' as subreddit,
                   d.doc_metadata->>'score' as score, d.doc_metadata->>'num_comments' as num_comments
            FROM documents d
            WHERE d.source_id = 3
            ORDER BY d.created_at DESC
            LIMIT 5
        """)
        
        print(f"Found {len(result)} Reddit documents:\n")
        
        for row in result:
            print(f"ID: {row['id']}")
            print(f"Title: {row['title'][:80]}...")
            print(f"External ID: {row['external_id']}")
            print(f"Subreddit: r/{row['subreddit']}")
            print(f"Score: {row['score']} | Comments: {row['num_comments']}")
            print("-" * 80)

if __name__ == "__main__":
    asyncio.run(test_reddit_docs())