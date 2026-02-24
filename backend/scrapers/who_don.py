from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime
from loguru import logger
import feedparser

from .base import BaseScraper
from models.schemas import DocumentCreate

try:
    from newspaper import Article
    HAS_NEWSPAPER = True
except ImportError:
    HAS_NEWSPAPER = False
    logger.warning("newspaper4k not installed - will use RSS snippets only")


class WHODiseaseOutbreakNewsScraper(BaseScraper):
    """Scraper for WHO Disease Outbreak News"""

    def __init__(self, source_id: int = None):
        super().__init__(
            source_id=source_id or 0,
            source_name="WHO Disease Outbreak News",
            rate_limit=0.5  # 0.5 requests per second (be respectful)
        )
        self.rss_url = "https://www.who.int/feeds/entity/don/en/rss.xml"

    async def search(self, disease_term: str, **kwargs) -> List[Dict[str, Any]]:
        """Search WHO Disease Outbreak News RSS for disease-related articles"""
        if not disease_term:
            logger.warning("No disease term provided for WHO DON search")
            return []

        logger.info(f"Fetching WHO Disease Outbreak News for: {disease_term}")

        try:
            await self.rate_limiter.acquire()

            # Fetch RSS feed
            response = await self.client.get(self.rss_url)
            response.raise_for_status()

            # Parse RSS feed
            feed = feedparser.parse(response.text)

            # Filter entries that match the disease term
            disease_lower = disease_term.lower()
            results = []

            for entry in feed.entries:
                title = entry.get('title', '').lower()
                description = entry.get('summary', '').lower()

                # Check if disease term is mentioned
                if disease_lower in title or disease_lower in description:
                    article_url = entry.get('link', '')
                    article_text = ''

                    # Try to extract full article text
                    if HAS_NEWSPAPER and article_url:
                        try:
                            await self.rate_limiter.acquire()
                            article = Article(article_url)
                            article.download()
                            article.parse()
                            article_text = article.text or ''
                            logger.debug(f"Extracted {len(article_text)} chars from {article_url}")
                        except Exception as e:
                            logger.debug(f"Could not extract article from {article_url}: {e}")

                    article_data = {
                        'title': entry.get('title', ''),
                        'link': article_url,
                        'published': entry.get('published', ''),
                        'published_parsed': entry.get('published_parsed'),
                        'description': entry.get('summary', ''),
                        'id': entry.get('id', entry.get('link', '')),
                        'article_text': article_text,
                    }
                    results.append(article_data)

            logger.info(f"Found {len(results)} WHO DON articles for '{disease_term}'")
            return results

        except Exception as e:
            logger.error(f"Error fetching WHO DON for '{disease_term}': {e}")
            return []

    async def fetch_details(self, external_id: str) -> Dict[str, Any]:
        """WHO DON RSS doesn't require detail fetching - all data in search"""
        return {}

    def extract_document_data(self, raw_data: Dict[str, Any]) -> Tuple[DocumentCreate, Optional[datetime]]:
        """Extract and transform WHO DON article data"""

        # Build unique ID from link
        article_id = raw_data.get('id', raw_data.get('link', ''))

        # Use full article text if available, otherwise RSS snippet
        article_text = raw_data.get('article_text', '')
        if article_text:
            content = article_text
            summary = article_text[:500]
        else:
            content = raw_data.get('description', raw_data.get('title', ''))
            summary = content[:500]

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
            'published_date': published_date,
            'who_url': raw_data.get('link', ''),
            'has_full_text': bool(article_text),
        }

        # Build title
        title = raw_data.get('title', 'Untitled WHO DON Article')

        return DocumentCreate(
            source_id=self.source_id,
            external_id=article_id,
            url=raw_data.get('link', ''),
            title=title,
            content=content,
            summary=summary,
            metadata=metadata
        ), source_updated_at
