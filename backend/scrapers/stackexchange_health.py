from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime
from loguru import logger
from urllib.parse import quote_plus
import re

from .base import BaseScraper
from models.schemas import DocumentCreate


class StackExchangeHealthScraper(BaseScraper):
    """Scraper for Stack Exchange Health sites with cursor-based resume"""

    def __init__(self, source_id: int = None):
        super().__init__(
            source_id=source_id or 0,
            source_name="Stack Exchange Health",
            rate_limit=30.0
        )
        self.api_url = "https://api.stackexchange.com/2.3"

    async def search(self, disease_term: str, **kwargs) -> List[Dict[str, Any]]:
        """Search Stack Exchange Health sites with cursor-based resume"""
        if not disease_term:
            return []

        max_results = kwargs.get('max_results')  # None = unlimited

        # Load cursor
        cursor = await self.get_cursor(disease_term)
        saved_page = cursor.get('page', 1)
        saved_site_idx = cursor.get('site_idx', 0)
        exhausted = cursor.get('exhausted', False)

        if exhausted:
            logger.info(f"StackExchange: Exhausted for '{disease_term}', incremental")
            saved_page = 1
            saved_site_idx = 0

        results = []
        sites = ['health', 'medicalsciences']

        for site_idx, site in enumerate(sites):
            if site_idx < saved_site_idx:
                continue
            start_page = saved_page if site_idx == saved_site_idx else 1
            try:
                site_results = await self._search_site(disease_term, site, max_results, start_page)
                results.extend(site_results)
                # Save progress after each site
                await self.save_cursor(disease_term, site_idx=site_idx + 1, page=1)
            except Exception as e:
                logger.warning(f"Error searching {site} site: {e}")

        if not results or (max_results and len(results) < max_results):
            await self.mark_exhausted(disease_term)

        logger.info(f"Found {len(results)} questions on Stack Exchange for '{disease_term}'")
        return results

    async def _search_site(self, disease_term: str, site: str, max_results: int = None,
                           start_page: int = 1) -> List[Dict[str, Any]]:
        """Search a specific Stack Exchange site with page resume"""
        all_results = []
        page = start_page
        has_more = True

        while has_more and (max_results is None or len(all_results) < max_results):
            page_size = 100 if max_results is None else min(100, max_results - len(all_results))
            params = {
                'order': 'desc', 'sort': 'relevance',
                'intitle': disease_term, 'site': site,
                'pagesize': page_size, 'page': page,
                'filter': 'withbody'
            }

            try:
                await self.rate_limiter.acquire()
                response = await self.make_request(f"{self.api_url}/search", params=params)
                items = response.get('items', [])
                all_results.extend(items)

                has_more = response.get('has_more', False)
                page += 1

                quota_remaining = response.get('quota_remaining', 0)
                if quota_remaining < 100:
                    logger.warning(f"Stack Exchange quota low: {quota_remaining}")
                    break

            except Exception as e:
                logger.error(f"Error fetching page {page} from {site}: {e}")
                break

        # Fetch top answers
        for item in all_results:
            if item.get('answer_count', 0) > 0 and item.get('accepted_answer_id'):
                try:
                    answer = await self._fetch_answer(item['accepted_answer_id'], site)
                    if answer:
                        item['top_answer'] = answer
                except Exception:
                    pass
            item['se_site'] = site

        return all_results

    async def _fetch_answer(self, answer_id: int, site: str) -> Optional[str]:
        try:
            await self.rate_limiter.acquire()
            params = {'site': site, 'filter': 'withbody'}
            response = await self.make_request(f"{self.api_url}/answers/{answer_id}", params=params)
            items = response.get('items', [])
            if items and items[0].get('body'):
                body = re.sub('<[^<]+?>', '', items[0]['body'])
                return body[:1000]
        except Exception:
            pass
        return None

    async def fetch_details(self, question_id: str) -> Dict[str, Any]:
        return {}

    def extract_document_data(self, raw_data: Dict[str, Any]) -> Tuple[DocumentCreate, Optional[datetime]]:
        question_id = raw_data.get('question_id', '')
        site = raw_data.get('se_site', 'health')

        body = re.sub('<[^<]+?>', '', raw_data.get('body', ''))

        content_parts = []
        if raw_data.get('title'):
            content_parts.append(f"QUESTION: {raw_data['title']}")
        if body:
            content_parts.append(f"BODY: {body[:2000]}")
        content_parts.append(f"SCORE: {raw_data.get('score', 0)}")
        content_parts.append(f"ANSWERS: {raw_data.get('answer_count', 0)}")
        if raw_data.get('tags'):
            content_parts.append(f"TAGS: {', '.join(raw_data['tags'])}")
        if raw_data.get('top_answer'):
            content_parts.append("\nTOP ANSWER:")
            content_parts.append(raw_data['top_answer'])

        content = "\n\n".join(content_parts)
        summary = raw_data.get('title', '')
        if body:
            summary += f" - {body[:200]}"
        summary = summary[:500]

        source_updated_at = None
        creation_date = None
        if raw_data.get('creation_date'):
            try:
                source_updated_at = datetime.fromtimestamp(raw_data['creation_date'])
                creation_date = source_updated_at.strftime("%Y-%m-%d")
            except:
                pass
        if raw_data.get('last_activity_date'):
            try:
                last_activity = datetime.fromtimestamp(raw_data['last_activity_date'])
                if not source_updated_at or last_activity > source_updated_at:
                    source_updated_at = last_activity
            except:
                pass

        metadata = {
            'question_id': question_id, 'site': site,
            'score': raw_data.get('score', 0),
            'answer_count': raw_data.get('answer_count', 0),
            'tags': raw_data.get('tags', []),
            'is_answered': raw_data.get('is_answered', False),
            'accepted_answer_id': raw_data.get('accepted_answer_id'),
            'view_count': raw_data.get('view_count', 0),
            'creation_date': creation_date,
            'top_answer': raw_data.get('top_answer', ''),
        }

        url = raw_data.get('link', f"https://{site}.stackexchange.com/questions/{question_id}")

        return DocumentCreate(
            source_id=self.source_id,
            external_id=f"se_{site}_{question_id}",
            url=url, title=raw_data.get('title', 'Untitled Question'),
            content=content, summary=summary, metadata=metadata
        ), source_updated_at
