"""MyHealthTeam scraper with cursor-based resume.
MyHealthTeam runs sites like MyMSTeam.com, MyALSTeam.com etc.
"""
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime
from loguru import logger
from urllib.parse import quote_plus
from bs4 import BeautifulSoup
import re

from .base import BaseScraper
from models.schemas import DocumentCreate


MYHEALTHTEAM_SITES = {
    'multiple sclerosis': {'url': 'https://www.mymsteam.com', 'name': 'MyMSTeam'},
    'ms': {'url': 'https://www.mymsteam.com', 'name': 'MyMSTeam'},
    'als': {'url': 'https://www.myalsteam.com', 'name': 'MyALSTeam'},
    'amyotrophic lateral sclerosis': {'url': 'https://www.myalsteam.com', 'name': 'MyALSTeam'},
    'lupus': {'url': 'https://www.mylupusteam.com', 'name': 'MyLupusTeam'},
    'crohn': {'url': 'https://www.mycrohnsteam.com', 'name': 'MyCrohnsTeam'},
}


class MyHealthTeamScraper(BaseScraper):
    """Scraper for MyHealthTeam community resources with cursor-based resume"""

    def __init__(self, source_id: int = None):
        super().__init__(
            source_id=source_id or 0,
            source_name="MyHealthTeam",
            rate_limit=0.5
        )

    async def search(self, disease_term: str, **kwargs) -> List[Dict[str, Any]]:
        """Scrape MyHealthTeam resources with cursor-based resume into URL list"""
        max_results = kwargs.get('max_results')  # None = unlimited
        logger.info(f"Searching MyHealthTeam for: {disease_term}")

        # Load cursor
        cursor = await self.get_cursor(disease_term)
        url_index = cursor.get('url_index', 0)
        exhausted = cursor.get('exhausted', False)

        # Find matching site
        term_lower = disease_term.lower()
        site = None
        for key, s in MYHEALTHTEAM_SITES.items():
            if key in term_lower or term_lower in key:
                site = s
                break
        if not site:
            slug = term_lower.replace(' ', '').replace("'", '')
            site = {'url': f'https://www.my{slug}team.com', 'name': f'My{disease_term}Team'}

        results = []

        try:
            # Get sitemap URLs
            sitemap_urls = await self._fetch_sitemap_urls(site['url'])
            if not sitemap_urls:
                sitemap_urls = await self._scrape_resource_links(site['url'])
            if not sitemap_urls:
                logger.info(f"No MyHealthTeam site found for '{disease_term}'")
                return []

            logger.info(f"Found {len(sitemap_urls)} resource URLs from {site['name']}, starting at index {url_index}")

            # Resume from saved index
            urls_to_fetch = sitemap_urls[url_index:]
            if max_results is not None:
                urls_to_fetch = urls_to_fetch[:max_results]

            for i, url in enumerate(urls_to_fetch):
                try:
                    article = await self._fetch_article(url, site['name'])
                    if article:
                        results.append(article)
                except Exception as e:
                    logger.debug(f"Error fetching {url}: {e}")

                # Save cursor every 10 articles
                current_index = url_index + i + 1
                if (i + 1) % 10 == 0:
                    await self.save_cursor(disease_term, url_index=current_index)

            # Save final cursor
            final_index = url_index + len(urls_to_fetch)
            await self.save_cursor(disease_term, url_index=final_index)

            if final_index >= len(sitemap_urls):
                await self.mark_exhausted(disease_term)

        except Exception as e:
            logger.error(f"Error scraping MyHealthTeam for '{disease_term}': {e}")
            await self.save_cursor(disease_term, url_index=url_index)

        logger.info(f"Found {len(results)} resources from {site['name']} for '{disease_term}'")
        return results

    async def _fetch_sitemap_urls(self, base_url: str) -> List[str]:
        urls = []
        try:
            await self.rate_limiter.acquire()
            response = await self.client.get(f"{base_url}/resources_sitemap_0.xml", timeout=15)
            if response.status_code == 200:
                soup = BeautifulSoup(response.text, 'lxml-xml')
                for loc in soup.find_all('loc'):
                    url = loc.text.strip()
                    if '/resources/' in url and not url.endswith('/resources/'):
                        urls.append(url)
        except Exception as e:
            logger.debug(f"Error fetching sitemap from {base_url}: {e}")
        return urls

    async def _scrape_resource_links(self, base_url: str) -> List[str]:
        urls = []
        try:
            await self.rate_limiter.acquire()
            response = await self.client.get(f"{base_url}/resources/questions-and-answers", timeout=15)
            if response.status_code == 200:
                soup = BeautifulSoup(response.text, 'html.parser')
                for link in soup.find_all('a', href=True):
                    href = link['href']
                    if '/resources/' in href and href not in urls:
                        full_url = href if href.startswith('http') else f"{base_url}{href}"
                        urls.append(full_url)
        except Exception as e:
            logger.debug(f"Error scraping resource links from {base_url}: {e}")
        return urls

    async def _fetch_article(self, url: str, site_name: str) -> Optional[Dict[str, Any]]:
        try:
            await self.rate_limiter.acquire()
            response = await self.client.get(url, timeout=15)
            if response.status_code != 200:
                return None

            soup = BeautifulSoup(response.text, 'html.parser')

            title = ''
            h1 = soup.find('h1')
            if h1:
                title = h1.get_text(strip=True)
            if not title:
                title_tag = soup.find('title')
                if title_tag:
                    title = title_tag.get_text(strip=True).split('|')[0].strip()
            if not title or len(title) < 5:
                return None

            html_tag = soup.find('html')
            lang = html_tag.get('lang', 'en') if html_tag else 'en'
            if lang and not lang.startswith('en'):
                return None

            content = ''
            for selector in ['article', '.article-body', '.resource-body',
                           '.post-content', 'main article', '[class*="article"]']:
                elem = soup.select_one(selector)
                if elem:
                    content = elem.get_text(separator='\n', strip=True)
                    break
            if not content:
                main = soup.find('main') or soup.find('article') or soup
                paragraphs = main.find_all('p')
                content = '\n\n'.join(p.get_text(strip=True) for p in paragraphs if len(p.get_text(strip=True)) > 20)
            if not content or len(content) < 100:
                return None

            author = ''
            author_elem = soup.find(['span', 'div', 'a'], class_=re.compile(r'author|byline|writer'))
            if author_elem:
                author = author_elem.get_text(strip=True)

            date_str = ''
            date_elem = soup.find('time') or soup.find(['span', 'div'], class_=re.compile(r'date|published|updated'))
            if date_elem:
                date_str = date_elem.get('datetime') or date_elem.get_text(strip=True)

            meta_desc = ''
            meta = soup.find('meta', attrs={'name': 'description'})
            if meta:
                meta_desc = meta.get('content', '')

            return {
                'url': url, 'title': title, 'content': content[:20000],
                'author': author, 'date': date_str,
                'site_name': site_name, 'description': meta_desc,
            }
        except Exception as e:
            logger.debug(f"Error fetching article {url}: {e}")
            return None

    async def fetch_details(self, external_id: str) -> Dict[str, Any]:
        return {}

    def extract_document_data(self, raw_data: Dict[str, Any]) -> Tuple[DocumentCreate, Optional[datetime]]:
        url = raw_data.get('url', '')
        slug = url.rstrip('/').split('/')[-1] if url else 'unknown'
        site_slug = raw_data.get('site_name', 'mht').lower().replace(' ', '')
        external_id = f"myhealthteam_{site_slug}_{slug}"

        content_parts = []
        if raw_data.get('title'):
            content_parts.append(f"TITLE: {raw_data['title']}")
        if raw_data.get('content'):
            content_parts.append(f"CONTENT: {raw_data['content']}")
        if raw_data.get('author'):
            content_parts.append(f"AUTHOR: {raw_data['author']}")
        if raw_data.get('site_name'):
            content_parts.append(f"SOURCE: {raw_data['site_name']}")

        content = "\n\n".join(content_parts)
        summary = raw_data.get('description') or ''
        if not summary and raw_data.get('content'):
            summary = raw_data['content'][:500]
        summary = summary[:500]

        source_updated_at = None
        posted_date = None
        if raw_data.get('date'):
            try:
                date_str = raw_data['date'].split('T')[0]
                source_updated_at = datetime.fromisoformat(date_str)
                posted_date = source_updated_at.strftime("%Y-%m-%d")
            except:
                pass

        metadata = {
            'community': raw_data.get('site_name', 'MyHealthTeam'),
            'author': raw_data.get('author', ''),
            'reply_count': 0, 'posted_date': posted_date,
        }

        return DocumentCreate(
            source_id=self.source_id, external_id=external_id,
            url=url, title=raw_data.get('title', 'Untitled'),
            content=content, summary=summary, metadata=metadata
        ), source_updated_at
