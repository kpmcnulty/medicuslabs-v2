from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime
from loguru import logger
from urllib.parse import quote_plus
import re

from .base import BaseScraper
from models.schemas import DocumentCreate


class StackExchangeHealthScraper(BaseScraper):
    """Scraper for Stack Exchange Health & Medical Sciences sites"""

    def __init__(self, source_id: int = None):
        super().__init__(
            source_id=source_id or 0,
            source_name="Stack Exchange Health",
            rate_limit=30.0  # Stack Exchange API allows 30 requests per second
        )
        self.api_url = "https://api.stackexchange.com/2.3"

    async def search(self, disease_term: str, **kwargs) -> List[Dict[str, Any]]:
        """Search Stack Exchange Health sites for disease-related questions"""
        if not disease_term:
            logger.warning("No disease term provided for Stack Exchange search")
            return []

        # Get max results from kwargs
        max_results = kwargs.get('max_results') or 100

        results = []

        # Search both health and medicalsciences sites
        sites = ['health', 'medicalsciences']

        for site in sites:
            try:
                site_results = await self._search_site(disease_term, site, max_results // 2)
                results.extend(site_results)
            except Exception as e:
                logger.warning(f"Error searching {site} site: {e}")
                continue

        logger.info(f"Found {len(results)} questions on Stack Exchange for '{disease_term}'")
        return results

    async def _search_site(self, disease_term: str, site: str, max_results: int) -> List[Dict[str, Any]]:
        """Search a specific Stack Exchange site"""
        all_results = []
        page = 1
        has_more = True

        while has_more and len(all_results) < max_results:
            params = {
                'order': 'desc',
                'sort': 'relevance',
                'intitle': disease_term,
                'site': site,
                'pagesize': min(100, max_results - len(all_results)),
                'page': page,
                'filter': 'withbody'  # Include question body
            }

            try:
                await self.rate_limiter.acquire()

                response = await self.make_request(f"{self.api_url}/search", params=params)

                items = response.get('items', [])
                all_results.extend(items)

                # Check if there are more pages
                has_more = response.get('has_more', False)
                page += 1

                # Check quota
                quota_remaining = response.get('quota_remaining', 0)
                if quota_remaining < 100:
                    logger.warning(f"Stack Exchange quota low: {quota_remaining} remaining")
                    break

            except Exception as e:
                logger.error(f"Error fetching page {page} from {site}: {e}")
                break

        # Fetch top answer for each question
        for item in all_results:
            if item.get('answer_count', 0) > 0 and item.get('accepted_answer_id'):
                try:
                    answer = await self._fetch_answer(item['accepted_answer_id'], site)
                    if answer:
                        item['top_answer'] = answer
                except Exception as e:
                    logger.warning(f"Error fetching answer: {e}")

            # Add site information
            item['se_site'] = site

        return all_results

    async def _fetch_answer(self, answer_id: int, site: str) -> Optional[str]:
        """Fetch answer body"""
        try:
            await self.rate_limiter.acquire()

            params = {
                'site': site,
                'filter': 'withbody'
            }

            response = await self.make_request(f"{self.api_url}/answers/{answer_id}", params=params)

            items = response.get('items', [])
            if items and items[0].get('body'):
                # Strip HTML tags from body
                body = items[0]['body']
                body = re.sub('<[^<]+?>', '', body)  # Remove HTML tags
                return body[:1000]  # Limit to 1000 chars

        except Exception as e:
            logger.warning(f"Error fetching answer {answer_id}: {e}")

        return None

    async def fetch_details(self, question_id: str) -> Dict[str, Any]:
        """Fetch detailed question information"""
        # Details are already fetched in search
        return {}

    def extract_document_data(self, raw_data: Dict[str, Any]) -> Tuple[DocumentCreate, Optional[datetime]]:
        """Extract and transform Stack Exchange question data"""

        question_id = raw_data.get('question_id', '')
        site = raw_data.get('se_site', 'health')

        # Strip HTML tags from body
        body = raw_data.get('body', '')
        body = re.sub('<[^<]+?>', '', body)  # Remove HTML tags

        # Build content
        content_parts = []

        if raw_data.get('title'):
            content_parts.append(f"QUESTION: {raw_data['title']}")

        if body:
            content_parts.append(f"BODY: {body[:2000]}")  # Limit body length

        content_parts.append(f"SCORE: {raw_data.get('score', 0)}")
        content_parts.append(f"ANSWERS: {raw_data.get('answer_count', 0)}")

        if raw_data.get('tags'):
            content_parts.append(f"TAGS: {', '.join(raw_data['tags'])}")

        # Add top answer if available
        if raw_data.get('top_answer'):
            content_parts.append("\nTOP ANSWER:")
            content_parts.append(raw_data['top_answer'])

        content = "\n\n".join(content_parts)

        # Summary - title + first part of body
        summary = raw_data.get('title', '')
        if body:
            summary += f" - {body[:200]}"
        summary = summary[:500]

        # Parse creation date
        source_updated_at = None
        creation_date = None

        if raw_data.get('creation_date'):
            try:
                # Stack Exchange uses Unix timestamp
                timestamp = raw_data['creation_date']
                source_updated_at = datetime.fromtimestamp(timestamp)
                creation_date = source_updated_at.strftime("%Y-%m-%d")
            except Exception as e:
                logger.warning(f"Error parsing timestamp {timestamp}: {e}")

        # Check for last activity date (more recent)
        if raw_data.get('last_activity_date'):
            try:
                timestamp = raw_data['last_activity_date']
                last_activity = datetime.fromtimestamp(timestamp)
                if not source_updated_at or last_activity > source_updated_at:
                    source_updated_at = last_activity
            except Exception as e:
                logger.warning(f"Error parsing last activity timestamp: {e}")

        # Build metadata
        metadata = {
            'question_id': question_id,
            'site': site,
            'score': raw_data.get('score', 0),
            'answer_count': raw_data.get('answer_count', 0),
            'tags': raw_data.get('tags', []),
            'is_answered': raw_data.get('is_answered', False),
            'accepted_answer_id': raw_data.get('accepted_answer_id'),
            'view_count': raw_data.get('view_count', 0),
            'creation_date': creation_date,
            'top_answer': raw_data.get('top_answer', ''),
        }

        # Build URL
        url = raw_data.get('link', f"https://{site}.stackexchange.com/questions/{question_id}")

        title = raw_data.get('title', 'Untitled Question')

        return DocumentCreate(
            source_id=self.source_id,
            external_id=f"se_{site}_{question_id}",
            url=url,
            title=title,
            content=content,
            summary=summary,
            metadata=metadata
        ), source_updated_at
