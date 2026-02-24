from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime
from loguru import logger
from urllib.parse import quote

from .base import BaseScraper
from models.schemas import DocumentCreate


class WikipediaScraper(BaseScraper):
    """Scraper for Wikipedia Medical articles"""

    def __init__(self, source_id: int = None):
        super().__init__(
            source_id=source_id or 0,
            source_name="Wikipedia",
            rate_limit=1.0  # 1 request per second (respectful)
        )
        self.base_url = "https://en.wikipedia.org/api/rest_v1"

    async def search(self, disease_term: str, **kwargs) -> List[Dict[str, Any]]:
        """Search Wikipedia for disease article"""
        if not disease_term:
            logger.warning("No disease term provided for Wikipedia search")
            return []

        logger.info(f"Fetching Wikipedia article for: {disease_term}")

        try:
            # URL-encode the disease term
            encoded_term = quote(disease_term)

            # First, get the page summary to check if it exists
            summary_url = f"{self.base_url}/page/summary/{encoded_term}"
            summary_data = await self.make_request(summary_url)

            if not summary_data or summary_data.get('type') == 'https://mediawiki.org/wiki/HyperSwitch/errors/not_found':
                logger.info(f"No Wikipedia article found for '{disease_term}'")
                return []

            # Get the full HTML content
            html_url = f"{self.base_url}/page/html/{encoded_term}"

            try:
                html_response = await self.client.get(html_url)
                html_response.raise_for_status()
                html_content = html_response.text
            except Exception as e:
                logger.warning(f"Could not fetch HTML content: {e}")
                html_content = ''

            # Combine summary and HTML data
            article_data = {
                'page_id': summary_data.get('pageid', ''),
                'title': summary_data.get('title', ''),
                'description': summary_data.get('description', ''),
                'extract': summary_data.get('extract', ''),
                'extract_html': summary_data.get('extract_html', ''),
                'thumbnail': summary_data.get('thumbnail', {}),
                'content_urls': summary_data.get('content_urls', {}),
                'timestamp': summary_data.get('timestamp', ''),
                'html_content': html_content,
            }

            logger.info(f"Found Wikipedia article for '{disease_term}'")
            return [article_data]

        except Exception as e:
            logger.error(f"Error fetching Wikipedia article for '{disease_term}': {e}")
            return []

    async def fetch_details(self, external_id: str) -> Dict[str, Any]:
        """Wikipedia API returns all data in search - no detail fetching needed"""
        return {}

    def extract_document_data(self, raw_data: Dict[str, Any]) -> Tuple[DocumentCreate, Optional[datetime]]:
        """Extract and transform Wikipedia article data"""

        # Page ID is the unique identifier
        page_id = raw_data.get('page_id', '')
        external_id = f"wikipedia_{page_id}"

        # Extract content
        title = raw_data.get('title', 'Untitled Article')
        extract = raw_data.get('extract', '')
        html_content = raw_data.get('html_content', '')

        # Use extract as content (plain text summary)
        # Full HTML is available in metadata if needed
        content = extract
        summary = extract[:500] if len(extract) > 500 else extract

        # Parse last modified timestamp
        source_updated_at = None
        timestamp_str = raw_data.get('timestamp', '')
        if timestamp_str:
            try:
                # ISO format: 2023-01-15T12:34:56Z
                source_updated_at = datetime.fromisoformat(timestamp_str.replace('Z', '+00:00'))
            except Exception as e:
                logger.warning(f"Error parsing timestamp '{timestamp_str}': {e}")

        # Build metadata
        metadata = {
            'page_id': page_id,
            'last_modified': timestamp_str,
            'description': raw_data.get('description', ''),
            'thumbnail_url': raw_data.get('thumbnail', {}).get('source', ''),
            'has_html_content': bool(html_content),
            'desktop_url': raw_data.get('content_urls', {}).get('desktop', {}).get('page', ''),
            'mobile_url': raw_data.get('content_urls', {}).get('mobile', {}).get('page', ''),
        }

        # Build URL
        url = metadata.get('desktop_url') or f"https://en.wikipedia.org/wiki/{title.replace(' ', '_')}"

        return DocumentCreate(
            source_id=self.source_id,
            external_id=external_id,
            url=url,
            title=title,
            content=content,
            summary=summary,
            metadata=metadata
        ), source_updated_at
