from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime
from loguru import logger
from urllib.parse import quote_plus
import re

from .base import BaseScraper
from models.schemas import DocumentCreate


class WHODiseaseOutbreakNewsScraper(BaseScraper):
    """Scraper for WHO Disease Outbreak News with cursor-based resume.
    
    WHO DON API returns limited results (~100). We mark exhausted after one pass
    and do incremental on subsequent runs.
    """

    API_URL = "https://www.who.int/api/news/diseaseoutbreaknews"

    def __init__(self, source_id: int = None):
        super().__init__(
            source_id=source_id or 0,
            source_name="WHO Disease Outbreak News",
            rate_limit=0.5
        )

    def _strip_html(self, html: str) -> str:
        if not html:
            return ''
        return re.sub(r'<[^>]+>', '', html).strip()

    async def search(self, disease_term: str, **kwargs) -> List[Dict[str, Any]]:
        if not disease_term:
            return []

        max_results = kwargs.get('max_results')  # None = unlimited

        # Load cursor
        cursor = await self.get_cursor(disease_term)
        newest_seen = cursor.get('newest_seen')
        exhausted = cursor.get('exhausted', False)

        logger.info(f"Fetching WHO DON for: {disease_term}")

        try:
            await self.rate_limiter.acquire()
            # WHO API returns up to ~100 results, paginate with $skip
            all_results = []
            skip = 0
            page_size = 100

            while max_results is None or len(all_results) < max_results:
                url = f"{self.API_URL}?sf_culture=en&$orderby=PublicationDateAndTime%20desc&$top={page_size}&$skip={skip}"
                response = await self.client.get(url)
                response.raise_for_status()
                data = response.json()

                items = data.get('value', [])
                if not items:
                    await self.mark_exhausted(disease_term)
                    break

                disease_lower = disease_term.lower()
                for item in items:
                    title = (item.get('Title') or '').lower()
                    summary = self._strip_html(item.get('Summary') or '')
                    response_text = self._strip_html(item.get('Response') or '')
                    full_text = f"{title} {summary} {response_text}".lower()

                    if disease_lower in full_text:
                        item['_summary_clean'] = summary
                        item['_response_clean'] = response_text
                        all_results.append(item)

                        # Track newest
                        pub_date = item.get('PublicationDate')
                        if pub_date and (not newest_seen or pub_date > newest_seen):
                            newest_seen = pub_date

                        if max_results is not None and len(all_results) >= max_results:
                            break

                skip += page_size
                # Save cursor after each page
                await self.save_cursor(disease_term, newest_seen=newest_seen, skip=skip)

                if len(items) < page_size:
                    await self.mark_exhausted(disease_term)
                    break

            logger.info(f"Found {len(all_results)} WHO DON articles for '{disease_term}'")
            return all_results

        except Exception as e:
            logger.error(f"Error fetching WHO DON for '{disease_term}': {e}")
            await self.save_cursor(disease_term, newest_seen=newest_seen)
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
            title=title, content=content,
            summary=content[:500], metadata=metadata
        ), source_updated_at
