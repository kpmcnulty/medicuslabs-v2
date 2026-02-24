from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime
from loguru import logger
from urllib.parse import quote_plus
from bs4 import BeautifulSoup

from .base import BaseScraper
from models.schemas import DocumentCreate


class DrugsComScraper(BaseScraper):
    """Scraper for Drugs.com drug information"""

    def __init__(self, source_id: int = None):
        super().__init__(
            source_id=source_id or 0,
            source_name="Drugs.com",
            rate_limit=0.5  # 0.5 requests per second (be respectful)
        )
        self.base_url = "https://www.drugs.com"

    async def search(self, disease_term: str, **kwargs) -> List[Dict[str, Any]]:
        """Search Drugs.com for drugs related to a disease"""
        if not disease_term:
            logger.warning("No disease term provided for Drugs.com search")
            return []

        logger.info(f"Searching Drugs.com for: {disease_term}")

        try:
            # Search URL
            search_url = f"{self.base_url}/search.php"
            params = {'searchterm': disease_term}

            await self.rate_limiter.acquire()
            response = await self.client.get(search_url, params=params)
            response.raise_for_status()

            # Parse search results
            soup = BeautifulSoup(response.text, 'html.parser')

            results = []
            # Look for drug links in search results
            # Drugs.com search results typically have links in .ddc-search-results or similar
            drug_links = soup.select('a[href^="/"]')

            seen_urls = set()
            for link in drug_links:
                href = link.get('href', '')

                # Filter for drug pages (typically /drug-name.html or /mtm/drug-name.html)
                if href and (href.endswith('.html') or '/mtm/' in href or '/sfx/' in href):
                    full_url = f"{self.base_url}{href}"

                    # Avoid duplicates
                    if full_url in seen_urls:
                        continue
                    seen_urls.add(full_url)

                    # Fetch drug page details
                    try:
                        await self.rate_limiter.acquire()
                        drug_response = await self.client.get(full_url)
                        drug_response.raise_for_status()

                        drug_data = self._parse_drug_page(full_url, drug_response.text)
                        if drug_data:
                            results.append(drug_data)

                        # Limit to avoid too many requests
                        if len(results) >= 20:
                            break

                    except Exception as e:
                        logger.debug(f"Error fetching drug page {full_url}: {e}")

            logger.info(f"Found {len(results)} drugs on Drugs.com for '{disease_term}'")
            return results

        except Exception as e:
            logger.error(f"Error searching Drugs.com for '{disease_term}': {e}")
            return []

    def _parse_drug_page(self, url: str, html: str) -> Optional[Dict[str, Any]]:
        """Parse a Drugs.com drug page to extract information"""
        try:
            soup = BeautifulSoup(html, 'html.parser')

            # Extract drug name from title or h1
            drug_name = ''
            title_tag = soup.find('title')
            if title_tag:
                drug_name = title_tag.text.split('|')[0].strip()

            if not drug_name:
                h1_tag = soup.find('h1')
                if h1_tag:
                    drug_name = h1_tag.text.strip()

            if not drug_name:
                logger.debug(f"Could not extract drug name from {url}")
                return None

            # Extract description/indication
            description = ''
            # Look for "What is [drug]?" section
            desc_section = soup.find('h2', string=lambda text: text and 'What is' in text)
            if desc_section:
                desc_p = desc_section.find_next('p')
                if desc_p:
                    description = desc_p.get_text(strip=True)

            # Extract side effects
            side_effects = ''
            side_effects_section = soup.find('h2', string=lambda text: text and 'side effects' in text.lower() if text else False)
            if side_effects_section:
                side_effects_list = side_effects_section.find_next('ul')
                if side_effects_list:
                    side_effects = side_effects_list.get_text(separator='\n', strip=True)

            # Extract drug interactions
            interactions = ''
            interactions_section = soup.find('h2', string=lambda text: text and 'interaction' in text.lower() if text else False)
            if interactions_section:
                interactions_p = interactions_section.find_next('p')
                if interactions_p:
                    interactions = interactions_p.get_text(strip=True)

            # Extract dosage info
            dosage = ''
            dosage_section = soup.find('h2', string=lambda text: text and 'dosage' in text.lower() if text else False)
            if dosage_section:
                dosage_p = dosage_section.find_next('p')
                if dosage_p:
                    dosage = dosage_p.get_text(strip=True)

            # Extract drug class (if available)
            drug_class = ''
            class_tag = soup.find('b', string='Drug class:')
            if class_tag:
                drug_class = class_tag.find_next('a').get_text(strip=True) if class_tag.find_next('a') else ''

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
        """Drugs.com scraper fetches all data during search - no detail fetching needed"""
        return {}

    def extract_document_data(self, raw_data: Dict[str, Any]) -> Tuple[DocumentCreate, Optional[datetime]]:
        """Extract and transform Drugs.com drug data"""

        # Build unique ID from URL
        url = raw_data.get('url', '')
        drug_name = raw_data.get('drug_name', 'Unknown Drug')

        # Generate external_id from drug name
        external_id = f"drugscom_{drug_name.lower().replace(' ', '_').replace('.', '')}"

        # Build content from extracted sections
        content_parts = []

        description = raw_data.get('description', '')
        if description:
            content_parts.append(f"DESCRIPTION:\n{description}")

        side_effects = raw_data.get('side_effects', '')
        if side_effects:
            content_parts.append(f"SIDE EFFECTS:\n{side_effects}")

        interactions = raw_data.get('interactions', '')
        if interactions:
            content_parts.append(f"INTERACTIONS:\n{interactions}")

        dosage = raw_data.get('dosage', '')
        if dosage:
            content_parts.append(f"DOSAGE:\n{dosage}")

        content = '\n\n---\n\n'.join(content_parts)
        summary = content[:500] if len(content) > 500 else content

        # Build metadata
        metadata = {
            'drug_name': drug_name,
            'drug_class': raw_data.get('drug_class', ''),
            'side_effects_summary': side_effects[:200] if side_effects else '',
            'interactions_count': len(interactions.split('\n')) if interactions else 0,
        }

        # No source_updated_at since Drugs.com doesn't provide last modified dates easily
        source_updated_at = None

        return DocumentCreate(
            source_id=self.source_id,
            external_id=external_id,
            url=url,
            title=drug_name,
            content=content,
            summary=summary,
            metadata=metadata
        ), source_updated_at
