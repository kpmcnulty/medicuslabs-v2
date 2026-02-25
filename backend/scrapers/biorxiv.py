from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime
from loguru import logger
from urllib.parse import quote_plus

from .base import BaseScraper
from models.schemas import DocumentCreate


class BioRxivScraper(BaseScraper):
    """Scraper for bioRxiv/medRxiv preprints with cursor-based resume"""

    def __init__(self, source_id: int = None):
        super().__init__(
            source_id=source_id or 0,
            source_name="bioRxiv/medRxiv",
            rate_limit=1.0
        )
        self.base_url = "https://api.biorxiv.org"

    async def search(self, disease_term: str, **kwargs) -> List[Dict[str, Any]]:
        """Search medRxiv with cursor-based resume"""
        if not disease_term:
            return []

        max_results = kwargs.get('max_results')  # None = unlimited

        # Load cursor
        cursor_state = await self.get_cursor(disease_term)
        saved_cursor = cursor_state.get('offset', 0)
        exhausted = cursor_state.get('exhausted', False)
        saved_start_date = cursor_state.get('start_date')

        end_date = datetime.now().strftime("%Y-%m-%d")
        
        if exhausted:
            # Incremental: only get preprints since last end_date
            start_date = cursor_state.get('end_date', end_date)
            saved_cursor = 0
            logger.info(f"bioRxiv: Exhausted for '{disease_term}', incremental from {start_date}")
        else:
            start_date = saved_start_date or datetime.now().replace(year=datetime.now().year - 5).strftime("%Y-%m-%d")

        page_size = 100
        all_results = []

        logger.info(f"Searching medRxiv for: {disease_term} (cursor {saved_cursor}, {start_date} to {end_date})")

        try:
            cursor_offset = saved_cursor
            while max_results is None or len(all_results) < max_results:
                url = f"{self.base_url}/details/medrxiv/{start_date}/{end_date}/{cursor_offset}"

                try:
                    data = await self.make_request(url)

                    if not data or 'collection' not in data:
                        await self.mark_exhausted(disease_term)
                        break

                    papers = data['collection']
                    if not papers:
                        await self.mark_exhausted(disease_term)
                        break

                    # Filter by disease term
                    disease_lower = disease_term.lower()
                    for paper in papers:
                        title = paper.get('title', '').lower()
                        abstract = paper.get('abstract', '').lower()
                        if disease_lower in title or disease_lower in abstract:
                            all_results.append(paper)

                    total = int(data.get('messages', [{}])[0].get('total', 0))
                    cursor_offset += page_size

                    # Save cursor after each page
                    await self.save_cursor(disease_term, offset=cursor_offset, 
                                          start_date=start_date, end_date=end_date)

                    if cursor_offset >= total:
                        await self.mark_exhausted(disease_term)
                        break

                except Exception as e:
                    logger.error(f"Error fetching page at cursor {cursor_offset}: {e}")
                    await self.save_cursor(disease_term, offset=cursor_offset,
                                          start_date=start_date, end_date=end_date)
                    break

            logger.info(f"Found {len(all_results)} medRxiv preprints for '{disease_term}'")
            return all_results

        except Exception as e:
            logger.error(f"Error searching medRxiv for '{disease_term}': {e}")
            return all_results

    async def fetch_details(self, external_id: str) -> Dict[str, Any]:
        return {}

    def extract_document_data(self, raw_data: Dict[str, Any]) -> Tuple[DocumentCreate, Optional[datetime]]:
        doi = raw_data.get('doi', '')
        title = raw_data.get('title', 'Untitled Preprint')
        abstract = raw_data.get('abstract', '')
        authors = raw_data.get('authors', '')
        category = raw_data.get('category', '')
        date_str = raw_data.get('date', '')

        content = abstract
        summary = abstract[:500] if len(abstract) > 500 else abstract

        source_updated_at = None
        if date_str:
            try:
                source_updated_at = datetime.strptime(date_str, "%Y-%m-%d")
            except Exception as e:
                logger.warning(f"Error parsing date '{date_str}': {e}")

        metadata = {
            'doi': doi, 'authors': authors, 'category': category,
            'preprint_date': date_str,
            'server': raw_data.get('server', 'medrxiv'),
            'published': raw_data.get('published', ''),
            'jatsxml': raw_data.get('jatsxml', ''),
        }

        url = f"https://doi.org/{doi}" if doi else "https://www.medrxiv.org"

        return DocumentCreate(
            source_id=self.source_id,
            external_id=f"medrxiv_{doi}",
            url=url, title=title, content=content,
            summary=summary, metadata=metadata
        ), source_updated_at
