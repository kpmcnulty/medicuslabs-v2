#!/usr/bin/env python3
"""Trigger FAERS scrape via Celery"""

from tasks.scrapers import scrape_faers

# Get source ID for FAERS
import asyncio
from core.database import get_pg_connection

async def get_faers_id():
    async with get_pg_connection() as conn:
        result = await conn.fetchrow("SELECT id FROM sources WHERE name = 'FDA FAERS'")
        return result['id'] if result else None

# Get FAERS source ID
source_id = asyncio.run(get_faers_id())
print(f"FAERS source ID: {source_id}")

# Queue the task
print("Queueing FAERS scrape task...")
result = scrape_faers.delay(
    disease_ids=[1, 2, 3],
    disease_names=["Multiple Sclerosis", "Amyotrophic Lateral Sclerosis", "Acute Myeloid Leukemia"],
    source_id=source_id,
    source_name="FDA FAERS",
    limit=10  # 10 results per disease for testing
)

print(f"Task queued with ID: {result.id}")
print("Check Flower at http://localhost:5555 to monitor progress")
print("Or check crawl_jobs table for results")