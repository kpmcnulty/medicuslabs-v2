from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime
from loguru import logger
from urllib.parse import quote_plus
from bs4 import BeautifulSoup

from .base import BaseScraper
from models.schemas import DocumentCreate


class DrugsComScraper(BaseScraper):
    """Scraper for Drugs.com drug information (uses Playwright for bot detection bypass)"""

    def __init__(self, source_id: int = None):
        super().__init__(
            source_id=source_id or 0,
            source_name="Drugs.com",
            rate_limit=0.3
        )
        self.base_url = "https://www.drugs.com"

    async def search(self, disease_term: str, **kwargs) -> List[Dict[str, Any]]:
        """Search Drugs.com using Playwright, then fetch individual drug pages"""
        if not disease_term:
            return []

        max_results = kwargs.get('max_results') or 20
        logger.info(f"Searching Drugs.com (browser) for: {disease_term}")

        try:
            # Get search results page
            search_url = f"{self.base_url}/search.php?searchterm={quote_plus(disease_term)}"
            html = await self.fetch_with_browser(search_url, wait_selector='.ddc-search-results', wait_ms=3000)
            if not html:
                return []

            soup = BeautifulSoup(html, 'html.parser')
            results = []

            # Extract search result links — actual drug/condition pages
            search_results = soup.select('.ddc-search-result a.ddc-search-result-link-wrap')
            drug_urls = []
            for link in search_results:
                href = link.get('href', '')
                if href and not any(skip in href for skip in ['/answers/', '/news/', '/search', '#']):
                    full_url = href if href.startswith('http') else f"{self.base_url}{href}"
                    drug_urls.append(full_url)

            # Also grab individual drug links from news/list sections
            for link in soup.select('.ddc-search-result a[href$=".html"]'):
                href = link.get('href', '')
                if href and '/news/' not in href and '/search' not in href and '/answers/' not in href:
                    full_url = href if href.startswith('http') else f"{self.base_url}{href}"
                    if full_url not in drug_urls:
                        drug_urls.append(full_url)

            logger.info(f"Found {len(drug_urls)} drug page URLs to fetch")

            # Fetch each drug page
            for url in drug_urls[:max_results]:
                try:
                    drug_html = await self.fetch_with_browser(url, wait_ms=2000)
                    if drug_html:
                        drug_data = self._parse_drug_page(url, drug_html)
                        if drug_data:
                            results.append(drug_data)
                except Exception as e:
                    logger.debug(f"Error fetching drug page {url}: {e}")

            logger.info(f"Found {len(results)} drugs on Drugs.com for '{disease_term}'")
            return results

        except Exception as e:
            logger.error(f"Error searching Drugs.com for '{disease_term}': {e}")
            return []

    def _parse_drug_page(self, url: str, html: str) -> Optional[Dict[str, Any]]:
        """Parse a Drugs.com drug page"""
        try:
            soup = BeautifulSoup(html, 'html.parser')

            # Extract drug name
            drug_name = ''
            h1_tag = soup.find('h1')
            if h1_tag:
                drug_name = h1_tag.text.strip()
            if not drug_name:
                title_tag = soup.find('title')
                if title_tag:
                    drug_name = title_tag.text.split('|')[0].split('-')[0].strip()
            if not drug_name or len(drug_name) < 2:
                return None

            # Extract description
            description = ''
            desc_section = soup.find('h2', string=lambda t: t and 'What is' in t)
            if desc_section:
                desc_p = desc_section.find_next('p')
                if desc_p:
                    description = desc_p.get_text(strip=True)
            # Fallback: first paragraph in main content
            if not description:
                main = soup.select_one('.ddc-main-content, #content, main')
                if main:
                    first_p = main.find('p')
                    if first_p:
                        description = first_p.get_text(strip=True)

            # Extract side effects
            side_effects = ''
            se_section = soup.find('h2', string=lambda t: t and 'side effects' in t.lower() if t else False)
            if se_section:
                se_list = se_section.find_next('ul')
                if se_list:
                    side_effects = se_list.get_text(separator='\n', strip=True)

            # Extract interactions
            interactions = ''
            int_section = soup.find('h2', string=lambda t: t and 'interaction' in t.lower() if t else False)
            if int_section:
                int_p = int_section.find_next('p')
                if int_p:
                    interactions = int_p.get_text(strip=True)

            # Extract dosage
            dosage = ''
            dos_section = soup.find('h2', string=lambda t: t and 'dosage' in t.lower() if t else False)
            if dos_section:
                dos_p = dos_section.find_next('p')
                if dos_p:
                    dosage = dos_p.get_text(strip=True)

            # Extract drug class
            drug_class = ''
            class_tag = soup.find('b', string='Drug class:')
            if class_tag:
                class_link = class_tag.find_next('a')
                if class_link:
                    drug_class = class_link.get_text(strip=True)

            return {
                'url': url,
                'drug_name': drug_name,
                'description': description,
                'side_effects': side_effects,
                'interactions': interactions,
                'dosage': dosage,
                'drug_class': drug_class,
            }

        except Exception as e:
            logger.debug(f"Error parsing drug page {url}: {e}")
            return None

    async def fetch_details(self, external_id: str) -> Dict[str, Any]:
        return {}

    def extract_document_data(self, raw_data: Dict[str, Any]) -> Tuple[DocumentCreate, Optional[datetime]]:
        drug_name = raw_data.get('drug_name', 'Unknown Drug')
        external_id = f"drugscom_{drug_name.lower().replace(' ', '_').replace('.', '')}"

        content_parts = []
        for section, key in [('DESCRIPTION', 'description'), ('SIDE EFFECTS', 'side_effects'),
                             ('INTERACTIONS', 'interactions'), ('DOSAGE', 'dosage')]:
            if raw_data.get(key):
                content_parts.append(f"{section}:\n{raw_data[key]}")

        content = '\n\n---\n\n'.join(content_parts)
        summary = content[:500] if len(content) > 500 else content

        metadata = {
            'drug_name': drug_name,
            'drug_class': raw_data.get('drug_class', ''),
            'side_effects_summary': raw_data.get('side_effects', '')[:200],
        }

        return DocumentCreate(
            source_id=self.source_id,
            external_id=external_id,
            url=raw_data.get('url', ''),
            title=drug_name,
            content=content,
            summary=summary,
            metadata=metadata
        ), None
