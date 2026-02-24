from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime
from loguru import logger
from bs4 import BeautifulSoup
from urllib.parse import quote_plus
import re

from .base import BaseScraper
from models.schemas import DocumentCreate


class HealthUnlockedScraper(BaseScraper):
    """Scraper for HealthUnlocked community posts"""

    def __init__(self, source_id: int = None):
        super().__init__(
            source_id=source_id or 0,
            source_name="HealthUnlocked",
            rate_limit=0.5  # 0.5 requests per second (respectful)
        )
        self.base_url = "https://healthunlocked.com"

    async def search(self, disease_term: str, **kwargs) -> List[Dict[str, Any]]:
        """Search HealthUnlocked for disease-related posts"""
        if not disease_term:
            logger.warning("No disease term provided for HealthUnlocked search")
            return []

        # Get max results from kwargs
        max_results = kwargs.get('max_results') or 50

        # Build search URL
        encoded_term = quote_plus(disease_term)
        url = f"{self.base_url}/search/{encoded_term}"

        logger.info(f"Searching HealthUnlocked for: {disease_term}")

        try:
            await self.rate_limiter.acquire()

            # Fetch search results
            response = await self.client.get(url, follow_redirects=True)
            response.raise_for_status()

            # Parse HTML
            soup = BeautifulSoup(response.text, 'lxml')

            results = []

            # Find post elements - HealthUnlocked uses various selectors
            # This is a basic implementation - may need adjustment based on actual HTML structure
            posts = soup.find_all(['article', 'div'], class_=re.compile(r'post|item|result'), limit=max_results)

            if not posts:
                # Try alternative selectors
                posts = soup.find_all('div', attrs={'data-post-id': True}, limit=max_results)

            for post in posts[:max_results]:
                try:
                    post_data = await self._extract_post_data(post, soup, disease_term)
                    if post_data:
                        results.append(post_data)
                except Exception as e:
                    logger.warning(f"Error extracting post data: {e}")
                    continue

            logger.info(f"Found {len(results)} posts on HealthUnlocked for '{disease_term}'")
            return results

        except Exception as e:
            logger.error(f"Error searching HealthUnlocked for '{disease_term}': {e}")
            return []

    async def _extract_post_data(self, post_element, soup, disease_term: str) -> Optional[Dict[str, Any]]:
        """Extract post data from HTML element"""
        try:
            # Extract title
            title_elem = post_element.find(['h1', 'h2', 'h3', 'a'], class_=re.compile(r'title|heading'))
            title = title_elem.get_text(strip=True) if title_elem else 'Untitled Post'

            # Extract link
            link_elem = post_element.find('a', href=True)
            if link_elem and link_elem.get('href'):
                link = link_elem['href']
                if not link.startswith('http'):
                    link = f"{self.base_url}{link}"
            else:
                link = f"{self.base_url}/search/{quote_plus(disease_term)}"

            # Extract post ID from link
            post_id_match = re.search(r'/posts?/([a-zA-Z0-9_-]+)', link)
            post_id = post_id_match.group(1) if post_id_match else link

            # Extract author
            author_elem = post_element.find(['span', 'div', 'a'], class_=re.compile(r'author|user'))
            author = author_elem.get_text(strip=True) if author_elem else 'Anonymous'

            # Extract community
            community_elem = post_element.find(['span', 'a'], class_=re.compile(r'community|group'))
            community = community_elem.get_text(strip=True) if community_elem else disease_term

            # Extract content/excerpt
            content_elem = post_element.find(['p', 'div'], class_=re.compile(r'content|excerpt|description|summary'))
            content = content_elem.get_text(strip=True) if content_elem else ''

            # Extract reply count
            reply_elem = post_element.find(['span', 'div'], class_=re.compile(r'reply|comment|response'))
            reply_count = 0
            if reply_elem:
                reply_text = reply_elem.get_text(strip=True)
                reply_match = re.search(r'(\d+)', reply_text)
                if reply_match:
                    reply_count = int(reply_match.group(1))

            # Extract date
            date_elem = post_element.find(['time', 'span'], class_=re.compile(r'date|time'))
            date_str = None
            if date_elem:
                if date_elem.get('datetime'):
                    date_str = date_elem['datetime']
                else:
                    date_str = date_elem.get_text(strip=True)

            return {
                'post_id': post_id,
                'title': title,
                'link': link,
                'author': author,
                'community': community,
                'content': content,
                'reply_count': reply_count,
                'date': date_str,
                'top_replies': []  # Would need to fetch post details for replies
            }

        except Exception as e:
            logger.warning(f"Error extracting post element: {e}")
            return None

    async def fetch_details(self, post_id: str) -> Dict[str, Any]:
        """Fetch detailed post information including replies"""
        # Optional: implement if needed for full post details
        return {}

    def extract_document_data(self, raw_data: Dict[str, Any]) -> Tuple[DocumentCreate, Optional[datetime]]:
        """Extract and transform HealthUnlocked post data"""

        post_id = raw_data.get('post_id', raw_data.get('link', ''))

        # Build content
        content_parts = []

        if raw_data.get('title'):
            content_parts.append(f"TITLE: {raw_data['title']}")

        if raw_data.get('content'):
            content_parts.append(f"CONTENT: {raw_data['content']}")

        if raw_data.get('author'):
            content_parts.append(f"AUTHOR: {raw_data['author']}")

        if raw_data.get('community'):
            content_parts.append(f"COMMUNITY: {raw_data['community']}")

        content_parts.append(f"REPLIES: {raw_data.get('reply_count', 0)}")

        # Add top replies if available
        if raw_data.get('top_replies'):
            content_parts.append("\nTOP REPLIES:")
            for i, reply in enumerate(raw_data['top_replies'][:5], 1):
                content_parts.append(f"\n{i}. {reply.get('author', 'Anonymous')}:")
                content_parts.append(f"   {reply.get('content', '')[:500]}...")

        content = "\n\n".join(content_parts)

        # Summary
        summary = raw_data.get('title', '')
        if raw_data.get('content'):
            summary += f" - {raw_data['content'][:200]}"
        summary = summary[:500]

        # Parse date
        source_updated_at = None
        posted_date = None

        if raw_data.get('date'):
            try:
                # Try multiple date formats
                date_str = raw_data['date']
                for fmt in ['%Y-%m-%dT%H:%M:%S', '%Y-%m-%d', '%d %b %Y', '%B %d, %Y']:
                    try:
                        source_updated_at = datetime.strptime(date_str.split('.')[0].split('+')[0], fmt)
                        posted_date = source_updated_at.strftime("%Y-%m-%d")
                        break
                    except:
                        continue
            except Exception as e:
                logger.warning(f"Error parsing date '{raw_data.get('date')}': {e}")

        # Build metadata
        metadata = {
            'post_id': post_id,
            'community': raw_data.get('community', ''),
            'author': raw_data.get('author', 'Anonymous'),
            'reply_count': raw_data.get('reply_count', 0),
            'posted_date': posted_date,
            'top_replies': raw_data.get('top_replies', [])
        }

        title = raw_data.get('title', 'Untitled Post')

        return DocumentCreate(
            source_id=self.source_id,
            external_id=f"healthunlocked_{post_id}",
            url=raw_data.get('link', ''),
            title=title,
            content=content,
            summary=summary,
            metadata=metadata
        ), source_updated_at
