from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime
from loguru import logger
from urllib.parse import quote_plus

from .base import BaseScraper
from models.schemas import DocumentCreate


class BioRxivScraper(BaseScraper):
    """Scraper for bioRxiv/medRxiv preprints"""

    def __init__(self, source_id: int = None):
        super().__init__(
            source_id=source_id or 0,
            source_name="bioRxiv/medRxiv",
            rate_limit=1.0  # 1 request per second
        )
        self.base_url = "https://api.biorxiv.org"

    async def search(self, disease_term: str, **kwargs) -> List[Dict[str, Any]]:
        """Search medRxiv for disease-related preprints"""
        if not disease_term:
            logger.warning("No disease term provided for bioRxiv search")
            return []

        # Use content API with date range to get recent preprints
        # Default to last 2 years of preprints
        end_date = datetime.now().strftime("%Y-%m-%d")
        start_date = datetime.now().replace(year=datetime.now().year - 2).strftime("%Y-%m-%d")

        # Get preprints in date range
        cursor = 0
        page_size = 100
        all_results = []

        logger.info(f"Searching medRxiv for: {disease_term}")

        try:
            # Fetch preprints page by page
            while True:
                url = f"{self.base_url}/details/medrxiv/{start_date}/{end_date}/{cursor}"

                try:
                    data = await self.make_request(url)

                    if not data or 'collection' not in data:
                        break

                    papers = data['collection']
                    if not papers:
                        break

                    # Filter by disease term in title or abstract
                    disease_lower = disease_term.lower()
                    filtered = []
                    for paper in papers:
                        title = paper.get('title', '').lower()
                        abstract = paper.get('abstract', '').lower()
                        if disease_lower in title or disease_lower in abstract:
                            filtered.append(paper)

                    all_results.extend(filtered)

                    # Check if we have more pages
                    total = int(data.get('messages', [{}])[0].get('total', 0))
                    if cursor + page_size >= total:
                        break

                    cursor += page_size

                    # Limit results to avoid too many requests
                    if len(all_results) >= 100:
                        logger.info(f"Reached 100 results limit for '{disease_term}'")
                        break

                except Exception as e:
                    logger.error(f"Error fetching page at cursor {cursor}: {e}")
                    break

            logger.info(f"Found {len(all_results)} medRxiv preprints for '{disease_term}'")
            return all_results

        except Exception as e:
            logger.error(f"Error searching medRxiv for '{disease_term}': {e}")
            return []

    async def fetch_details(self, external_id: str) -> Dict[str, Any]:
        """bioRxiv API returns all data in search - no detail fetching needed"""
        return {}

    def extract_document_data(self, raw_data: Dict[str, Any]) -> Tuple[DocumentCreate, Optional[datetime]]:
        """Extract and transform bioRxiv preprint data"""

        # DOI is the unique identifier
        doi = raw_data.get('doi', '')

        # Extract metadata
        title = raw_data.get('title', 'Untitled Preprint')
        abstract = raw_data.get('abstract', '')
        authors = raw_data.get('authors', '')
        category = raw_data.get('category', '')
        date_str = raw_data.get('date', '')  # Usually YYYY-MM-DD

        # Build content from abstract
        content = abstract
        summary = abstract[:500] if len(abstract) > 500 else abstract

        # Parse date
        source_updated_at = None
        if date_str:
            try:
                source_updated_at = datetime.strptime(date_str, "%Y-%m-%d")
            except Exception as e:
                logger.warning(f"Error parsing date '{date_str}': {e}")

        # Build metadata
        metadata = {
            'doi': doi,
            'authors': authors,
            'category': category,
            'preprint_date': date_str,
            'server': raw_data.get('server', 'medrxiv'),
            'published': raw_data.get('published', ''),
            'jatsxml': raw_data.get('jatsxml', ''),
        }

        # Build URL
        url = f"https://doi.org/{doi}" if doi else f"https://www.medrxiv.org"

        return DocumentCreate(
            source_id=self.source_id,
            external_id=f"medrxiv_{doi}",
            url=url,
            title=title,
            content=content,
            summary=summary,
            metadata=metadata
        ), source_updated_at
