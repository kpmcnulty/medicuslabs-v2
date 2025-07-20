import asyncio
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime, timedelta
import hashlib
import json
import yaml
from pathlib import Path
from urllib.parse import urljoin, urlparse
import re

from bs4 import BeautifulSoup
from playwright.async_api import async_playwright, Page, Browser
from fake_useragent import UserAgent
from robotexclusionrulesparser import RobotExclusionRulesParser
from loguru import logger
import httpx

from .base import BaseScraper
from models.schemas import DocumentCreate
from core.config import settings


class WebScraper(BaseScraper):
    """Flexible web scraper for forums and patient communities"""
    
    def __init__(self, config_name: str, source_id: Optional[int] = None):
        """
        Initialize web scraper with configuration
        
        Args:
            config_name: Name of configuration file (without extension)
            source_id: Override source_id from config
        """
        self.config = self._load_config(config_name)
        self.config_name = config_name
        
        # Initialize base scraper
        super().__init__(
            source_id=source_id or self.config.get('source_id', 99),
            source_name=self.config.get('site_name', config_name),
            rate_limit=self.config.get('rate_limit', 0.5)
        )
        
        # Web scraping specific attributes
        self.requires_js = self.config.get('requires_js', False)
        self.user_agent = UserAgent()
        self.browser: Optional[Browser] = None
        self.page: Optional[Page] = None
        self.robots_parser = RobotExclusionRulesParser()
        
        # Load selectors
        self.selectors = self.config.get('selectors', {})
        self.extraction_rules = self.config.get('extraction_rules', {})
        
        # Optional basic keyword filtering
        self.filter_keywords = self.config.get('filter_keywords', [])
        self.min_keyword_matches = self.config.get('min_keyword_matches', 0)
        
    def _load_config(self, config_name: str) -> Dict[str, Any]:
        """Load configuration from YAML file"""
        config_path = Path(__file__).parent / 'configs' / f'{config_name}.yaml'
        
        if not config_path.exists():
            raise FileNotFoundError(f"Configuration file not found: {config_path}")
        
        with open(config_path, 'r') as f:
            return yaml.safe_load(f)
    
    async def __aenter__(self):
        """Async context manager entry"""
        await super().__aenter__()
        
        if self.requires_js:
            playwright = await async_playwright().start()
            self.browser = await playwright.chromium.launch(headless=True)
            context = await self.browser.new_context(user_agent=self.user_agent.random)
            self.page = await context.new_page()
        
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit"""
        if self.browser:
            await self.browser.close()
        
        await super().__aexit__(exc_type, exc_val, exc_tb)
    
    async def check_robots_txt(self, url: str) -> bool:
        """Check if URL is allowed by robots.txt"""
        parsed_url = urlparse(url)
        robots_url = f"{parsed_url.scheme}://{parsed_url.netloc}/robots.txt"
        
        try:
            response = await self.client.get(robots_url)
            if response.status_code == 200:
                self.robots_parser.parse(response.text)
                return self.robots_parser.is_allowed(self.user_agent.random, url)
        except Exception as e:
            logger.warning(f"Could not check robots.txt for {robots_url}: {e}")
        
        return True  # Allow if can't check
    
    async def fetch_page(self, url: str) -> str:
        """Fetch page content, using Playwright if JavaScript is required"""
        # Check robots.txt
        if not await self.check_robots_txt(url):
            logger.warning(f"URL blocked by robots.txt: {url}")
            return ""
        
        # Rate limiting
        await self.rate_limiter.acquire()
        
        try:
            if self.requires_js and self.page:
                # Use Playwright for JavaScript-rendered content
                await self.page.goto(url, wait_until='networkidle')
                content = await self.page.content()
                
                # Wait for specific elements if configured
                if wait_selector := self.selectors.get('wait_for'):
                    try:
                        await self.page.wait_for_selector(wait_selector, timeout=5000)
                    except:
                        logger.warning(f"Wait selector not found: {wait_selector}")
                
                return content
            else:
                # Use httpx for static content
                headers = {'User-Agent': self.user_agent.random}
                response = await self.client.get(url, headers=headers)
                response.raise_for_status()
                return response.text
                
        except Exception as e:
            logger.error(f"Error fetching {url}: {e}")
            return ""
    
    def extract_with_selector(self, soup: BeautifulSoup, selector: str, 
                            attribute: Optional[str] = None) -> Optional[str]:
        """
        Extract content using CSS selector with optional attribute
        
        Selector format: "css_selector" or "css_selector@attribute"
        """
        if '@' in selector:
            selector, attribute = selector.split('@', 1)
        
        element = soup.select_one(selector)
        if not element:
            return None
        
        if attribute:
            return element.get(attribute)
        else:
            return element.get_text(strip=True)
    
    def extract_all_with_selector(self, soup: BeautifulSoup, selector: str,
                                attribute: Optional[str] = None) -> List[str]:
        """Extract all matching elements"""
        if '@' in selector:
            selector, attribute = selector.split('@', 1)
        
        elements = soup.select(selector)
        results = []
        
        for element in elements:
            if attribute:
                value = element.get(attribute)
            else:
                value = element.get_text(strip=True)
            
            if value:
                results.append(value)
        
        return results
    
    async def search(self, disease_term: str, max_pages: int = 10, **kwargs) -> List[Dict[str, Any]]:
        """Search for posts related to a disease term"""
        results = []
        
        # Build search URL
        search_url_template = self.selectors.get('search_url')
        if not search_url_template:
            logger.error(f"No search URL configured for {self.config_name}")
            return []
        
        # Format search URL
        search_url = search_url_template.format(query=disease_term)
        if not search_url.startswith('http'):
            search_url = urljoin(self.config['base_url'], search_url)
        
        current_url = search_url
        page_count = 0
        
        while current_url and page_count < max_pages:
            logger.info(f"Scraping page {page_count + 1}: {current_url}")
            
            # Fetch page
            content = await self.fetch_page(current_url)
            if not content:
                break
            
            soup = BeautifulSoup(content, 'lxml')
            
            # Extract posts
            post_elements = soup.select(self.selectors.get('post_list', 'article'))
            
            for post_elem in post_elements:
                try:
                    post_data = await self._extract_post(post_elem, soup)
                    if post_data:
                        # Optional basic keyword filtering
                        if self._passes_keyword_filter(post_data):
                            results.append(post_data)
                        else:
                            logger.debug(f"Post filtered out: {post_data.get('title', '')[:50]}")
                except Exception as e:
                    logger.error(f"Error extracting post: {e}")
            
            # Get next page
            next_selector = self.selectors.get('next_page')
            if next_selector:
                next_url = self.extract_with_selector(soup, next_selector)
                if next_url:
                    if not next_url.startswith('http'):
                        next_url = urljoin(self.config['base_url'], next_url)
                    current_url = next_url
                    page_count += 1
                else:
                    break
            else:
                break
        
        logger.info(f"Found {len(results)} posts for '{disease_term}'")
        return results
    
    async def _extract_post(self, post_elem: BeautifulSoup, 
                          page_soup: BeautifulSoup) -> Optional[Dict[str, Any]]:
        """Extract post data from element"""
        post_data = {}
        
        # Extract basic fields
        for field, selector in self.selectors.items():
            if field.startswith('post_') and not field.startswith('post_list'):
                field_name = field.replace('post_', '')
                value = self.extract_with_selector(post_elem, selector)
                if value:
                    post_data[field_name] = value
        
        # Get full post URL
        if post_data.get('url'):
            if not post_data['url'].startswith('http'):
                post_data['url'] = urljoin(self.config['base_url'], post_data['url'])
            
            # Fetch full post content and comments
            full_content = await self.fetch_page(post_data['url'])
            if full_content:
                post_soup = BeautifulSoup(full_content, 'lxml')
                
                # Extract full content if not already present
                if not post_data.get('content') and self.selectors.get('post_content'):
                    content = self.extract_with_selector(
                        post_soup, 
                        self.selectors['post_content']
                    )
                    if content:
                        post_data['content'] = content
                
                # Extract comments
                post_data['comments'] = await self._extract_comments(post_soup)
        
        # Process dates
        if post_data.get('date'):
            post_data['date'] = self._parse_date(post_data['date'])
        
        # Generate ID
        if not post_data.get('id'):
            # Generate ID from URL or content
            id_source = post_data.get('url', '') + post_data.get('title', '')
            post_data['id'] = hashlib.md5(id_source.encode()).hexdigest()[:16]
        
        return post_data
    
    async def _extract_comments(self, soup: BeautifulSoup) -> List[Dict[str, Any]]:
        """Extract comments from post page"""
        comments = []
        
        comments_container = self.selectors.get('comments_container')
        if not comments_container:
            return comments
        
        container = soup.select_one(comments_container)
        if not container:
            return comments
        
        comment_selector = self.selectors.get('comment_item', '.comment')
        comment_elements = container.select(comment_selector)
        
        for comment_elem in comment_elements:
            comment_data = {}
            
            # Extract comment fields
            for field in ['comment_author', 'comment_date', 'comment_text']:
                if selector := self.selectors.get(field):
                    value = self.extract_with_selector(comment_elem, selector)
                    if value:
                        field_name = field.replace('comment_', '')
                        comment_data[field_name] = value
            
            # Process comment date
            if comment_data.get('date'):
                comment_data['date'] = self._parse_date(comment_data['date'])
            
            if comment_data.get('text'):
                comments.append(comment_data)
        
        return comments
    
    def _parse_date(self, date_str: str) -> Optional[datetime]:
        """Parse date string according to extraction rules"""
        if not date_str:
            return None
        
        date_format = self.extraction_rules.get('date_format')
        
        # Try configured format first
        if date_format:
            try:
                return datetime.strptime(date_str, date_format)
            except:
                pass
        
        # Try common formats
        common_formats = [
            '%Y-%m-%d',
            '%Y-%m-%dT%H:%M:%S',
            '%Y-%m-%d %H:%M:%S',
            '%B %d, %Y',
            '%d %B %Y',
            '%d/%m/%Y',
            '%m/%d/%Y'
        ]
        
        for fmt in common_formats:
            try:
                return datetime.strptime(date_str, fmt)
            except:
                continue
        
        # Try relative dates (e.g., "2 days ago")
        relative_match = re.match(r'(\d+)\s+(second|minute|hour|day|week|month|year)s?\s+ago', date_str.lower())
        if relative_match:
            amount = int(relative_match.group(1))
            unit = relative_match.group(2)
            
            if unit == 'second':
                return datetime.now() - timedelta(seconds=amount)
            elif unit == 'minute':
                return datetime.now() - timedelta(minutes=amount)
            elif unit == 'hour':
                return datetime.now() - timedelta(hours=amount)
            elif unit == 'day':
                return datetime.now() - timedelta(days=amount)
            elif unit == 'week':
                return datetime.now() - timedelta(weeks=amount)
            elif unit == 'month':
                return datetime.now() - timedelta(days=amount * 30)
            elif unit == 'year':
                return datetime.now() - timedelta(days=amount * 365)
        
        logger.warning(f"Could not parse date: {date_str}")
        return None
    
    def _passes_keyword_filter(self, post_data: Dict[str, Any]) -> bool:
        """
        Simple keyword filter to reduce obvious non-medical content
        
        Returns True if post should be kept
        """
        if not self.filter_keywords or self.min_keyword_matches == 0:
            return True  # No filtering configured
        
        # Combine text fields for checking
        text_to_check = ' '.join([
            post_data.get('title', ''),
            post_data.get('content', ''),
            post_data.get('preview', '')
        ]).lower()
        
        # Count keyword matches
        matches = 0
        for keyword in self.filter_keywords:
            if keyword.lower() in text_to_check:
                matches += 1
                if matches >= self.min_keyword_matches:
                    return True
        
        return False
    
    async def fetch_details(self, external_id: str) -> Dict[str, Any]:
        """Fetch detailed information for a specific post"""
        # For web sources, external_id might be a URL
        if external_id.startswith('http'):
            content = await self.fetch_page(external_id)
            if content:
                soup = BeautifulSoup(content, 'lxml')
                return await self._extract_post(soup, soup)
        
        return {}
    
    def extract_document_data(self, raw_data: Dict[str, Any]) -> Tuple[DocumentCreate, Optional[datetime]]:
        """Transform raw post data into DocumentCreate schema"""
        # Build content from post and comments
        content_parts = []
        
        # Add main post content
        if raw_data.get('content'):
            content_parts.append(f"POST: {raw_data['content']}")
        
        # Add author info
        if raw_data.get('author'):
            content_parts.append(f"AUTHOR: {raw_data['author']}")
        
        # Add comments
        if raw_data.get('comments'):
            content_parts.append(f"\nCOMMENTS ({len(raw_data['comments'])}):")
            for i, comment in enumerate(raw_data['comments'], 1):
                comment_text = f"\n--- Comment {i}"
                if comment.get('author'):
                    comment_text += f" by {comment['author']}"
                if comment.get('date'):
                    comment_text += f" at {comment['date']}"
                comment_text += f" ---\n{comment.get('text', '')}"
                content_parts.append(comment_text)
        
        content = "\n\n".join(content_parts)
        
        # Create summary
        summary = raw_data.get('content', '')[:500] if raw_data.get('content') else raw_data.get('title', '')[:500]
        
        # Build metadata
        metadata = {
            'post_id': raw_data.get('id'),
            'author': raw_data.get('author'),
            'post_date': str(raw_data.get('date')) if raw_data.get('date') else None,
            'comment_count': len(raw_data.get('comments', [])),
            'source_type': 'forum',
            'forum_name': self.config.get('site_name')
        }
        
        # Add any extra fields
        for key, value in raw_data.items():
            if key not in ['title', 'content', 'url', 'date', 'author', 'comments', 'id']:
                metadata[key] = value
        
        # Get source update date (post date)
        source_updated_at = raw_data.get('date')
        
        return DocumentCreate(
            source_id=self.source_id,
            external_id=raw_data.get('id', raw_data.get('url', '')),
            url=raw_data.get('url', ''),
            title=raw_data.get('title', ''),
            content=content,
            summary=summary,
            metadata=metadata
        ), source_updated_at