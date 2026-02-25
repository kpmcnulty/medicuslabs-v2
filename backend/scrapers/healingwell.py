from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime
from loguru import logger
import re

from .base import BaseScraper
from models.schemas import DocumentCreate


class HealingWellScraper(BaseScraper):
    """Scraper for HealingWell.com community forums with cursor-based resume"""

    FORUM_MAP = {
        'multiple sclerosis': 17,
        'als': 9,
        'amyotrophic lateral sclerosis': 9,
        'leukemia': 14,
        'aml': 14,
        'fabry': None,
        'pku': None,
        'phenylketonuria': None,
    }

    def __init__(self, source_id: int = None):
        super().__init__(
            source_id=source_id or 0,
            source_name="HealingWell",
            rate_limit=0.5
        )
        self.base_url = "https://www.healingwell.com/community"

    async def search(self, disease_term: str, **kwargs) -> List[Dict[str, Any]]:
        if not disease_term:
            return []

        max_results = kwargs.get('max_results')  # None = unlimited
        
        term_lower = disease_term.lower()
        forum_id = None
        for key, fid in self.FORUM_MAP.items():
            if key in term_lower or term_lower in key:
                forum_id = fid
                break

        if not forum_id:
            logger.info(f"No HealingWell forum mapping for '{disease_term}'")
            return []

        # Load cursor
        cursor = await self.get_cursor(disease_term)
        saved_page = cursor.get('page', 1)
        exhausted = cursor.get('exhausted', False)

        if exhausted:
            logger.info(f"HealingWell: Exhausted for '{disease_term}', checking for new content")
            saved_page = 1

        results = []
        page = saved_page

        while max_results is None or len(results) < max_results:
            url = f"{self.base_url}/default.aspx?f={forum_id}&p={page}"
            try:
                html = await self.fetch_with_browser(url, wait_ms=3000)
                if not html:
                    await self.mark_exhausted(disease_term)
                    break

                title_pattern = r'<a\s+class="forum-title"\s+href="([^"]+)"[^>]*>([^<]+)</a>'
                matches = re.findall(title_pattern, html)

                if not matches:
                    await self.mark_exhausted(disease_term)
                    break

                for href, title in matches:
                    m_match = re.search(r'm=(\d+)', href)
                    msg_id = m_match.group(1) if m_match else str(hash(href))

                    results.append({
                        'id': msg_id,
                        'title': title.strip(),
                        'url': f"https://www.healingwell.com{href}" if href.startswith('/') else href,
                        'forum_id': forum_id,
                        'disease_term': disease_term,
                    })

                page += 1
                # Save cursor after each page
                await self.save_cursor(disease_term, page=page)

                if len(matches) < 10:
                    await self.mark_exhausted(disease_term)
                    break

            except Exception as e:
                logger.error(f"HealingWell fetch error page {page}: {e}")
                await self.save_cursor(disease_term, page=page)
                break

        logger.info(f"Found {len(results)} topics on HealingWell for '{disease_term}'")
        if max_results:
            return results[:max_results]
        return results

    async def fetch_details(self, external_id: str) -> Dict[str, Any]:
        return {}

    def extract_document_data(self, raw_data: Dict[str, Any]) -> Tuple[DocumentCreate, Optional[datetime]]:
        msg_id = raw_data.get('id', '')
        title = raw_data.get('title', 'Untitled')
        url = raw_data.get('url', '')
        disease_term = raw_data.get('disease_term', '')

        content = f"TOPIC: {title}\n\nForum: HealingWell {disease_term}"
        summary = title[:500]

        metadata = {
            'community': 'HealingWell', 'author': 'unknown',
            'reply_count': 0, 'posted_date': None,
            'forum_id': raw_data.get('forum_id'),
        }

        return DocumentCreate(
            source_id=self.source_id,
            external_id=f"healingwell_{msg_id}",
            url=url, title=title[:500],
            content=content, summary=summary, metadata=metadata
        ), None
