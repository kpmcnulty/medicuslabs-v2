"""Inspire.com patient community scraper with cursor-based resume.
Uses Playwright to bypass bot protection. Keeps per-run limit since browser is slow.
"""
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime
from loguru import logger
from urllib.parse import quote_plus
from bs4 import BeautifulSoup
import re

from .base import BaseScraper
from models.schemas import DocumentCreate


INSPIRE_GROUPS = {
    'multiple sclerosis': ['national-ms-society', 'multiple-sclerosis'],
    'ms': ['national-ms-society'],
    'als': ['als-association', 'amyotrophic-lateral-sclerosis'],
    'amyotrophic lateral sclerosis': ['als-association'],
    'aml': ['leukemia-lymphoma-society'],
    'acute myeloid leukemia': ['leukemia-lymphoma-society'],
    'fabry disease': ['national-fabry-disease-foundation'],
    'pku': ['national-pku-alliance'],
    'phenylketonuria': ['national-pku-alliance'],
    'alpha-1': ['alpha-1-foundation'],
}


class InspireScraper(BaseScraper):
    """Scraper for Inspire.com patient communities with cursor-based resume"""

    def __init__(self, source_id: int = None):
        super().__init__(
            source_id=source_id or 0,
            source_name="Inspire",
            rate_limit=0.3
        )
        self.base_url = "https://www.inspire.com"

    async def search(self, disease_term: str, **kwargs) -> List[Dict[str, Any]]:
        """Search Inspire with cursor-based resume. Browser-based so keeps reasonable limits."""
        max_results = kwargs.get('max_results')
        
        # Load cursor
        cursor = await self.get_cursor(disease_term)
        fetched_urls = set(cursor.get('fetched_urls', []))
        exhausted = cursor.get('exhausted', False)

        if exhausted:
            logger.info(f"Inspire: Exhausted for '{disease_term}', checking for new content")

        logger.info(f"Searching Inspire for: {disease_term}")
        results = []

        try:
            search_url = f"{self.base_url}/search?q={quote_plus(disease_term)}&type=discussions"
            html = await self.fetch_with_browser(search_url, wait_ms=4000)

            if html and '403' not in html[:500]:
                soup = BeautifulSoup(html, 'html.parser')
                discussion_links = soup.find_all('a', href=re.compile(r'/groups/.*/discussion/'))
                
                for link in discussion_links:
                    if len(results) >= max_results:
                        break
                    href = link.get('href', '')
                    title = link.get_text(strip=True)
                    full_url = href if href.startswith('http') else f"{self.base_url}{href}"
                    
                    if full_url in fetched_urls:
                        continue
                    
                    if href and title and len(title) > 5:
                        disc_data = await self._fetch_discussion(full_url, title)
                        if disc_data:
                            results.append(disc_data)
                            fetched_urls.add(full_url)

                if not results:
                    results = await self._browse_groups(disease_term, max_results, fetched_urls)
            else:
                results = await self._browse_groups(disease_term, max_results, fetched_urls)

        except Exception as e:
            logger.error(f"Error searching Inspire for '{disease_term}': {e}")

        # Save cursor
        await self.save_cursor(disease_term, fetched_urls=list(fetched_urls)[-300:])
        if not results:
            await self.mark_exhausted(disease_term)

        logger.info(f"Found {len(results)} discussions from Inspire for '{disease_term}'")
        return results

    async def _browse_groups(self, disease_term: str, max_results: int,
                             fetched_urls: set) -> List[Dict[str, Any]]:
        results = []
        term_lower = disease_term.lower()

        groups = []
        for key, slugs in INSPIRE_GROUPS.items():
            if key in term_lower or term_lower in key:
                groups.extend(slugs)

        for group_slug in groups:
            try:
                group_url = f"{self.base_url}/groups/{group_slug}"
                html = await self.fetch_with_browser(group_url, wait_ms=4000)

                if html and '403' not in html[:500]:
                    soup = BeautifulSoup(html, 'html.parser')
                    for link in soup.find_all('a', href=re.compile(r'/discussion/')):
                        href = link.get('href', '')
                        title = link.get_text(strip=True)
                        full_url = href if href.startswith('http') else f"{self.base_url}{href}"
                        
                        if full_url in fetched_urls:
                            continue
                        
                        if href and title and len(title) > 5:
                            disc_data = await self._fetch_discussion(full_url, title)
                            if disc_data:
                                results.append(disc_data)
                                fetched_urls.add(full_url)
                                if len(results) >= max_results:
                                    return results
            except Exception as e:
                logger.debug(f"Error browsing group {group_slug}: {e}")

        return results

    async def _fetch_discussion(self, url: str, title: str) -> Optional[Dict[str, Any]]:
        try:
            html = await self.fetch_with_browser(url, wait_ms=3000)
            if not html or '403' in html[:500]:
                return None

            soup = BeautifulSoup(html, 'html.parser')

            content = ''
            post_body = soup.find(['div', 'article'], class_=re.compile(r'post|message|content|body'))
            if post_body:
                content = post_body.get_text(separator='\n', strip=True)
            if not content or len(content) < 20:
                return None

            author = ''
            author_elem = soup.find(['span', 'a', 'div'], class_=re.compile(r'author|user|username'))
            if author_elem:
                author = author_elem.get_text(strip=True)

            date_str = ''
            date_elem = soup.find('time') or soup.find(['span'], class_=re.compile(r'date|time'))
            if date_elem:
                date_str = date_elem.get('datetime') or date_elem.get_text(strip=True)

            replies = []
            reply_elems = soup.find_all(['div', 'article'], class_=re.compile(r'reply|response|comment'))
            for reply in reply_elems[:10]:
                reply_text = reply.get_text(strip=True)[:1000]
                if reply_text and len(reply_text) > 10:
                    replies.append({'content': reply_text, 'author': 'Community Member'})

            group = ''
            breadcrumb = soup.find(['nav', 'div'], class_=re.compile(r'breadcrumb|group'))
            if breadcrumb:
                group = breadcrumb.get_text(strip=True)

            return {
                'url': url, 'title': title, 'content': content[:10000],
                'author': author, 'date': date_str, 'group': group,
                'reply_count': len(replies), 'replies': replies,
            }
        except Exception as e:
            logger.debug(f"Error fetching discussion {url}: {e}")
            return None

    async def fetch_details(self, external_id: str) -> Dict[str, Any]:
        return {}

    def extract_document_data(self, raw_data: Dict[str, Any]) -> Tuple[DocumentCreate, Optional[datetime]]:
        url = raw_data.get('url', '')
        slug = url.rstrip('/').split('/')[-1] if url else 'unknown'
        external_id = f"inspire_{slug}"

        content_parts = []
        if raw_data.get('title'):
            content_parts.append(f"TITLE: {raw_data['title']}")
        if raw_data.get('content'):
            content_parts.append(f"CONTENT: {raw_data['content']}")
        if raw_data.get('author'):
            content_parts.append(f"AUTHOR: {raw_data['author']}")
        if raw_data.get('group'):
            content_parts.append(f"GROUP: {raw_data['group']}")
        if raw_data.get('replies'):
            content_parts.append(f"\nREPLIES ({raw_data.get('reply_count', 0)}):")
            for i, reply in enumerate(raw_data['replies'][:10], 1):
                content_parts.append(f"\n{i}. {reply.get('author', 'anonymous')}:")
                content_parts.append(f"   {reply.get('content', '')[:500]}")

        content = "\n\n".join(content_parts)
        summary = raw_data.get('title', '')
        if raw_data.get('content'):
            summary += f" - {raw_data['content'][:200]}"
        summary = summary[:500]

        source_updated_at = None
        posted_date = None
        if raw_data.get('date'):
            try:
                date_str = raw_data['date'].split('T')[0].split('.')[0]
                source_updated_at = datetime.fromisoformat(date_str)
                posted_date = source_updated_at.strftime("%Y-%m-%d")
            except:
                pass

        metadata = {
            'community': raw_data.get('group', 'Inspire'),
            'author': raw_data.get('author', 'anonymous'),
            'reply_count': raw_data.get('reply_count', 0),
            'posted_date': posted_date,
        }

        return DocumentCreate(
            source_id=self.source_id, external_id=external_id,
            url=url, title=raw_data.get('title', 'Untitled'),
            content=content, summary=summary, metadata=metadata
        ), source_updated_at
