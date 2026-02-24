from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime
from loguru import logger
import feedparser
from urllib.parse import quote_plus

from .base import BaseScraper
from models.schemas import DocumentCreate


class GoogleNewsScraper(BaseScraper):
    """Scraper for Google News RSS feed"""

    def __init__(self, source_id: int = None):
        # Will be set by trigger API - default to placeholder
        super().__init__(
            source_id=source_id or 0,
            source_name="Google News",
            rate_limit=1.0  # 1 request per second
        )

    async def search(self, disease_term: str, **kwargs) -> List[Dict[str, Any]]:
        """Search Google News RSS for disease-related articles"""
        if not disease_term:
            logger.warning("No disease term provided for Google News search")
            return []

        # Build RSS URL
        query = f"{disease_term} medical"
        encoded_query = quote_plus(query)
        url = f"https://news.google.com/rss/search?q={encoded_query}&hl=en-US&gl=US&ceid=US:en"

        logger.info(f"Fetching Google News RSS for: {query}")

        try:
            await self.rate_limiter.acquire()

            # Fetch RSS feed using httpx
            response = await self.client.get(url)
            response.raise_for_status()

            # Parse RSS feed
            feed = feedparser.parse(response.text)

            results = []
            for entry in feed.entries:
                # Extract article data
                article_data = {
                    'title': entry.get('title', ''),
                    'link': entry.get('link', ''),
                    'published': entry.get('published', ''),
                    'published_parsed': entry.get('published_parsed'),
                    'source': entry.get('source', {}).get('title', 'Unknown'),
                    'description': entry.get('summary', ''),
                    'id': entry.get('id', entry.get('link', ''))
                }
                results.append(article_data)

            logger.info(f"Found {len(results)} news articles for '{query}'")
            return results

        except Exception as e:
            logger.error(f"Error fetching Google News RSS for '{disease_term}': {e}")
            return []

    async def fetch_details(self, external_id: str) -> Dict[str, Any]:
        """Google News RSS doesn't require detail fetching - all data in search"""
        return {}

    def extract_document_data(self, raw_data: Dict[str, Any]) -> Tuple[DocumentCreate, Optional[datetime]]:
        """Extract and transform Google News article data"""

        # Build unique ID from link
        article_id = raw_data.get('id', raw_data.get('link', ''))

        # Build content
        content_parts = []

        if raw_data.get('title'):
            content_parts.append(f"TITLE: {raw_data['title']}")

        if raw_data.get('description'):
            content_parts.append(f"DESCRIPTION: {raw_data['description']}")

        if raw_data.get('source'):
            content_parts.append(f"SOURCE: {raw_data['source']}")

        content = "\n\n".join(content_parts)

        # Summary is description
        summary = raw_data.get('description', raw_data.get('title', ''))[:500]

        # Parse publication date
        published_date = None
        source_updated_at = None

        if raw_data.get('published_parsed'):
            try:
                # published_parsed is a time.struct_time
                time_tuple = raw_data['published_parsed']
                source_updated_at = datetime(
                    time_tuple.tm_year,
                    time_tuple.tm_mon,
                    time_tuple.tm_mday,
                    time_tuple.tm_hour,
                    time_tuple.tm_min,
                    time_tuple.tm_sec
                )
                published_date = source_updated_at.strftime("%Y-%m-%d")
            except Exception as e:
                logger.warning(f"Error parsing publication date: {e}")

        # Build metadata
        metadata = {
            'publisher': raw_data.get('source', 'Unknown'),
            'published_date': published_date,
            'google_news_url': raw_data.get('link', ''),
            'description': raw_data.get('description', ''),
        }

        # Build title
        title = raw_data.get('title', 'Untitled Article')

        return DocumentCreate(
            source_id=self.source_id,
            external_id=article_id,
            url=raw_data.get('link', ''),
            title=title,
            content=content,
            summary=summary,
            metadata=metadata
        ), source_updated_at
