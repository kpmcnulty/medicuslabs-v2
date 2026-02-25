from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime
from loguru import logger
from bs4 import BeautifulSoup
from urllib.parse import quote_plus
import re

from .base import BaseScraper
from models.schemas import DocumentCreate


class MedicalNewsTodayScraper(BaseScraper):
    """Scraper for Medical News Today articles with cursor-based resume"""

    def __init__(self, source_id: int = None):
        super().__init__(
            source_id=source_id or 0,
            source_name="Medical News Today",
            rate_limit=0.5
        )
        self.base_url = "https://www.medicalnewstoday.com"

    async def search(self, disease_term: str, **kwargs) -> List[Dict[str, Any]]:
        """Search Medical News Today with cursor-based resume"""
        if not disease_term:
            return []

        max_results = kwargs.get('max_results')  # None = unlimited

        # Load cursor
        cursor = await self.get_cursor(disease_term)
        fetched_urls = set(cursor.get('fetched_urls', []))
        exhausted = cursor.get('exhausted', False)

        if exhausted:
            logger.info(f"MNT: Exhausted for '{disease_term}', running fresh search for new content")
            # Don't reset fetched_urls - they serve as dedup

        encoded_term = quote_plus(disease_term)
        url = f"{self.base_url}/search?q={encoded_term}"

        logger.info(f"Searching Medical News Today for: {disease_term}")

        try:
            await self.rate_limiter.acquire()
            response = await self.client.get(url, follow_redirects=True)
            response.raise_for_status()

            soup = BeautifulSoup(response.text, 'lxml')
            results = []

            article_links = []
            for link in soup.find_all('a', href=True):
                href = link['href']
                if '/articles/' in href and href not in article_links:
                    if not href.startswith('http'):
                        href = f"{self.base_url}{href}"
                    if href not in fetched_urls:
                        article_links.append(href)
                    if max_results is not None and len(article_links) >= max_results:
                        break

            if not article_links:
                await self.mark_exhausted(disease_term)

            for article_url in article_links:
                if max_results is not None and len(results) >= max_results:
                    break
                try:
                    article_data = await self._fetch_article(article_url)
                    if article_data:
                        results.append(article_data)
                        fetched_urls.add(article_url)
                        # Save cursor periodically (every 5 articles)
                        if len(results) % 5 == 0:
                            await self.save_cursor(disease_term, 
                                                  fetched_urls=list(fetched_urls)[-500:])  # Keep last 500
                except Exception as e:
                    logger.warning(f"Error fetching article {article_url}: {e}")
                    await self.save_cursor(disease_term, fetched_urls=list(fetched_urls)[-500:])
                    continue

            # Save final cursor
            await self.save_cursor(disease_term, fetched_urls=list(fetched_urls)[-500:])
            await self.mark_exhausted(disease_term)

            logger.info(f"Found {len(results)} articles on Medical News Today for '{disease_term}'")
            return results

        except Exception as e:
            logger.error(f"Error searching Medical News Today for '{disease_term}': {e}")
            await self.save_cursor(disease_term, fetched_urls=list(fetched_urls)[-500:])
            return []

    async def _fetch_article(self, url: str) -> Optional[Dict[str, Any]]:
        """Fetch full article content"""
        try:
            await self.rate_limiter.acquire()
            response = await self.client.get(url, follow_redirects=True)
            response.raise_for_status()

            soup = BeautifulSoup(response.text, 'lxml')

            article_id_match = re.search(r'/articles/(\d+)', url)
            article_id = article_id_match.group(1) if article_id_match else url

            title_elem = soup.find(['h1', 'meta'], attrs={'property': 'og:title'})
            if title_elem:
                title = title_elem.get('content', '') if title_elem.name == 'meta' else title_elem.get_text(strip=True)
            else:
                title = 'Untitled Article'

            author_elem = soup.find(['span', 'div', 'a'], class_=re.compile(r'author', re.I))
            if not author_elem:
                author_elem = soup.find('meta', attrs={'name': 'author'})
            author = ''
            if author_elem:
                author = author_elem.get('content', '') if author_elem.name == 'meta' else author_elem.get_text(strip=True)

            date_elem = soup.find('time', attrs={'datetime': True})
            if not date_elem:
                date_elem = soup.find('meta', attrs={'property': 'article:published_time'})
            published_date = None
            if date_elem:
                published_date = date_elem.get('content') if date_elem.name == 'meta' else date_elem.get('datetime')

            categories = []
            for cat in soup.find_all(['a', 'span'], class_=re.compile(r'category|tag', re.I))[:10]:
                cat_text = cat.get_text(strip=True)
                if cat_text and len(cat_text) > 1:
                    categories.append(cat_text)

            content_parts = []
            article_body = soup.find(['article', 'div'], class_=re.compile(r'article-body|content|post-content', re.I))
            if article_body:
                for p in article_body.find_all('p'):
                    text = p.get_text(strip=True)
                    if text and len(text) > 30:
                        content_parts.append(text)
            if not content_parts:
                for p in soup.find_all('p')[:50]:
                    text = p.get_text(strip=True)
                    if text and len(text) > 30:
                        content_parts.append(text)

            full_content = '\n\n'.join(content_parts[:30])

            return {
                'article_id': article_id, 'url': url, 'title': title,
                'author': author, 'published_date': published_date,
                'categories': categories, 'content': full_content,
            }

        except Exception as e:
            logger.warning(f"Error fetching article {url}: {e}")
            return None

    async def fetch_details(self, article_id: str) -> Dict[str, Any]:
        url = f"{self.base_url}/articles/{article_id}"
        return await self._fetch_article(url) or {}

    def extract_document_data(self, raw_data: Dict[str, Any]) -> Tuple[DocumentCreate, Optional[datetime]]:
        article_id = raw_data.get('article_id', raw_data.get('url', ''))

        content_parts = []
        if raw_data.get('title'):
            content_parts.append(f"TITLE: {raw_data['title']}")
        if raw_data.get('author'):
            content_parts.append(f"AUTHOR: {raw_data['author']}")
        if raw_data.get('content'):
            content_parts.append(f"CONTENT:\n{raw_data['content']}")
        if raw_data.get('categories'):
            content_parts.append(f"CATEGORIES: {', '.join(raw_data['categories'])}")

        content = "\n\n".join(content_parts)
        summary = raw_data.get('content', raw_data.get('title', ''))[:500]

        source_updated_at = None
        published_date_str = None
        if raw_data.get('published_date'):
            try:
                date_str = raw_data['published_date'].split('+')[0].split('Z')[0].split('.')[0]
                for fmt in ['%Y-%m-%dT%H:%M:%S', '%Y-%m-%d', '%d %B %Y', '%B %d, %Y']:
                    try:
                        source_updated_at = datetime.strptime(date_str, fmt)
                        published_date_str = source_updated_at.strftime("%Y-%m-%d")
                        break
                    except:
                        continue
            except:
                pass

        metadata = {
            'article_id': article_id, 'author': raw_data.get('author', ''),
            'published_date': published_date_str,
            'categories': raw_data.get('categories', []),
            'article_url': raw_data.get('url', ''),
        }

        return DocumentCreate(
            source_id=self.source_id,
            external_id=f"mnt_{article_id}",
            url=raw_data.get('url', ''),
            title=raw_data.get('title', 'Untitled Article'),
            content=content, summary=summary, metadata=metadata
        ), source_updated_at
