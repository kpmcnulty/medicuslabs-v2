from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime
from loguru import logger
from urllib.parse import quote_plus
import re

from .base import BaseScraper
from models.schemas import DocumentCreate


class WHODiseaseOutbreakNewsScraper(BaseScraper):
    """Scraper for WHO Disease Outbreak News via JSON API"""

    API_URL = "https://www.who.int/api/news/diseaseoutbreaknews"

    def __init__(self, source_id: int = None):
        super().__init__(
            source_id=source_id or 0,
            source_name="WHO Disease Outbreak News",
            rate_limit=0.5
        )

    def _strip_html(self, html: str) -> str:
        """Strip HTML tags"""
        if not html:
            return ''
        return re.sub(r'<[^>]+>', '', html).strip()

    async def search(self, disease_term: str, **kwargs) -> List[Dict[str, Any]]:
        if not disease_term:
            return []

        max_results = kwargs.get('max_results')
        logger.info(f"Fetching WHO DON for: {disease_term}")

        try:
            await self.rate_limiter.acquire()
            # Fetch all recent DON articles and filter by disease term
            url = f"{self.API_URL}?sf_culture=en&$orderby=PublicationDateAndTime%20desc&$top=100"
            response = await self.client.get(url)
            response.raise_for_status()
            data = response.json()

            disease_lower = disease_term.lower()
            results = []
            for item in data.get('value', []):
                title = (item.get('Title') or '').lower()
                summary = self._strip_html(item.get('Summary') or '')
                response_text = self._strip_html(item.get('Response') or '')
                full_text = f"{title} {summary} {response_text}".lower()

                if disease_lower in full_text:
                    item['_summary_clean'] = summary
                    item['_response_clean'] = response_text
                    results.append(item)
                    if max_results is not None and len(results) >= max_results:
                        break

            logger.info(f"Found {len(results)} WHO DON articles for '{disease_term}'")
            return results

        except Exception as e:
            logger.error(f"Error fetching WHO DON for '{disease_term}': {e}")
            return []

    async def fetch_details(self, external_id: str) -> Dict[str, Any]:
        return {}

    def extract_document_data(self, raw_data: Dict[str, Any]) -> Tuple[DocumentCreate, Optional[datetime]]:
        don_id = raw_data.get('UrlName', raw_data.get('Id', ''))
        title = raw_data.get('Title', 'Untitled WHO DON')

        summary = raw_data.get('_summary_clean', '')
        response_text = raw_data.get('_response_clean', '')
        content = f"{summary}\n\n{response_text}".strip() or title

        source_updated_at = None
        pub_date = raw_data.get('PublicationDate')
        if pub_date:
            try:
                source_updated_at = datetime.fromisoformat(pub_date.replace('Z', '+00:00')).replace(tzinfo=None)
            except (ValueError, TypeError):
                pass

        metadata = {
            'published_date': pub_date,
            'don_id': don_id,
            'who_url': f"https://www.who.int{raw_data.get('ItemDefaultUrl', '')}",
        }

        return DocumentCreate(
            source_id=self.source_id,
            external_id=f"who_don_{don_id}",
            url=f"https://www.who.int{raw_data.get('ItemDefaultUrl', '')}",
            title=title,
            content=content,
            summary=content[:500],
            metadata=metadata
        ), source_updated_at
