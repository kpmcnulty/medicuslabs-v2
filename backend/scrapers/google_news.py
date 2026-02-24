from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime
from loguru import logger
import feedparser
import asyncio
from urllib.parse import quote_plus

from .base import BaseScraper
from models.schemas import DocumentCreate

try:
    from googlenewsdecoder import new_decoderv1
    HAS_DECODER = True
except ImportError:
    HAS_DECODER = False
    logger.warning("googlenewsdecoder not installed - will use RSS snippets only")

try:
    from newspaper import Article
    HAS_NEWSPAPER = True
except ImportError:
    HAS_NEWSPAPER = False
    logger.warning("newspaper4k not installed - will use RSS snippets only")


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
                google_url = entry.get('link', '')
                real_url = google_url
                article_text = ''
                article_authors = []

                # Decode Google News redirect URL and extract full article
                if HAS_DECODER and HAS_NEWSPAPER and google_url:
                    try:
                        decoded = new_decoderv1(google_url)
                        if decoded.get('status'):
                            real_url = decoded['decoded_url']
                            await self.rate_limiter.acquire()
                            a = Article(real_url)
                            a.download()
                            a.parse()
                            article_text = a.text or ''
                            article_authors = a.authors or []
                            logger.debug(f"Extracted {len(article_text)} chars from {real_url}")
                    except Exception as e:
                        logger.debug(f"Could not extract article from {google_url}: {e}")

                article_data = {
                    'title': entry.get('title', ''),
                    'link': real_url,
                    'google_news_url': google_url,
                    'published': entry.get('published', ''),
                    'published_parsed': entry.get('published_parsed'),
                    'source': entry.get('source', {}).get('title', 'Unknown'),
                    'description': entry.get('summary', ''),
                    'id': entry.get('id', entry.get('link', '')),
                    'article_text': article_text,
                    'article_authors': article_authors,
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
            'publisher': raw_data.get('source', 'Unknown'),
            'published_date': published_date,
            'google_news_url': raw_data.get('google_news_url', ''),
            'authors': raw_data.get('article_authors', []),
            'has_full_text': bool(article_text),
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
