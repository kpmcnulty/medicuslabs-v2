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

try:
    from newspaper import Article
    HAS_NEWSPAPER = True
except ImportError:
    HAS_NEWSPAPER = False


class GoogleNewsScraper(BaseScraper):
    """Scraper for Google News RSS feed.
    
    Note: Google News RSS naturally caps at ~100 results per feed.
    We mark exhausted after one pass and do incremental on next run.
    """

    def __init__(self, source_id: int = None):
        super().__init__(
            source_id=source_id or 0,
            source_name="Google News",
            rate_limit=1.0
        )

    async def search(self, disease_term: str, **kwargs) -> List[Dict[str, Any]]:
        """Fetch Google News RSS. Marks exhausted after one pass (~100 items max from RSS)."""
        if not disease_term:
            return []

        # Google News RSS is inherently limited to ~100 results per query
        # No real pagination available, so we fetch once and mark exhausted
        cursor = await self.get_cursor(disease_term)
        newest_seen = cursor.get('newest_seen')

        query = f"{disease_term} medical"
        encoded_query = quote_plus(query)
        url = f"https://news.google.com/rss/search?q={encoded_query}&hl=en-US&gl=US&ceid=US:en"

        logger.info(f"Fetching Google News RSS for: {query}")

        try:
            await self.rate_limiter.acquire()
            response = await self.client.get(url)
            response.raise_for_status()

            feed = feedparser.parse(response.text)
            results = []

            for entry in feed.entries:
                google_url = entry.get('link', '')
                real_url = google_url
                article_text = ''
                article_authors = []

                # Skip articles we've already seen (incremental)
                pub_parsed = entry.get('published_parsed')
                if pub_parsed and newest_seen:
                    try:
                        entry_ts = datetime(*pub_parsed[:6]).isoformat()
                        if entry_ts <= newest_seen:
                            continue
                    except:
                        pass

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
                    except Exception as e:
                        logger.debug(f"Could not extract article from {google_url}: {e}")

                # Track newest
                if pub_parsed:
                    try:
                        entry_ts = datetime(*pub_parsed[:6]).isoformat()
                        if not newest_seen or entry_ts > newest_seen:
                            newest_seen = entry_ts
                    except:
                        pass

                results.append({
                    'title': entry.get('title', ''),
                    'link': real_url,
                    'google_news_url': google_url,
                    'published': entry.get('published', ''),
                    'published_parsed': pub_parsed,
                    'source': entry.get('source', {}).get('title', 'Unknown'),
                    'description': entry.get('summary', ''),
                    'id': entry.get('id', entry.get('link', '')),
                    'article_text': article_text,
                    'article_authors': article_authors,
                })

            # Mark exhausted (RSS is naturally capped at ~100)
            await self.save_cursor(disease_term, newest_seen=newest_seen)
            await self.mark_exhausted(disease_term)

            logger.info(f"Found {len(results)} news articles for '{query}'")
            return results

        except Exception as e:
            logger.error(f"Error fetching Google News RSS for '{disease_term}': {e}")
            if newest_seen:
                await self.save_cursor(disease_term, newest_seen=newest_seen)
            return []

    async def fetch_details(self, external_id: str) -> Dict[str, Any]:
        return {}

    def extract_document_data(self, raw_data: Dict[str, Any]) -> Tuple[DocumentCreate, Optional[datetime]]:
        article_id = raw_data.get('id', raw_data.get('link', ''))

        article_text = raw_data.get('article_text', '')
        if article_text:
            content = article_text
            summary = article_text[:500]
        else:
            content = raw_data.get('description', raw_data.get('title', ''))
            summary = content[:500]

        published_date = None
        source_updated_at = None

        if raw_data.get('published_parsed'):
            try:
                time_tuple = raw_data['published_parsed']
                source_updated_at = datetime(
                    time_tuple.tm_year, time_tuple.tm_mon, time_tuple.tm_mday,
                    time_tuple.tm_hour, time_tuple.tm_min, time_tuple.tm_sec
                )
                published_date = source_updated_at.strftime("%Y-%m-%d")
            except Exception as e:
                logger.warning(f"Error parsing publication date: {e}")

        metadata = {
            'publisher': raw_data.get('source', 'Unknown'),
            'published_date': published_date,
            'google_news_url': raw_data.get('google_news_url', ''),
            'authors': raw_data.get('article_authors', []),
            'has_full_text': bool(article_text),
        }

        title = raw_data.get('title', 'Untitled Article')

        return DocumentCreate(
            source_id=self.source_id,
            external_id=article_id,
            url=raw_data.get('link', ''),
            title=title, content=content,
            summary=summary, metadata=metadata
        ), source_updated_at
