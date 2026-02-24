from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime
from loguru import logger
from urllib.parse import quote_plus

from .base import BaseScraper
from models.schemas import DocumentCreate


class SemanticScholarScraper(BaseScraper):
    """Scraper for Semantic Scholar academic paper search API"""

    API_BASE = "https://api.semanticscholar.org/graph/v1"
    FIELDS = "title,abstract,authors,year,citationCount,journal,externalIds,url,publicationDate"

    def __init__(self, source_id: int = None):
        super().__init__(
            source_id=source_id or 0,
            source_name="Semantic Scholar",
            rate_limit=1.0  # 100 req/5min without key
        )

    async def search(self, disease_term: str, **kwargs) -> List[Dict[str, Any]]:
        if not disease_term:
            return []

        max_results = kwargs.get('max_results') or 100
        results = []
        offset = 0
        limit = min(100, max_results)  # API max is 100 per request

        while offset < max_results:
            await self.rate_limiter.acquire()
            url = (
                f"{self.API_BASE}/paper/search"
                f"?query={quote_plus(disease_term)}"
                f"&limit={limit}&offset={offset}"
                f"&fields={self.FIELDS}"
            )

            try:
                response = await self.client.get(url)
                if response.status_code == 429:
                    logger.warning("Semantic Scholar rate limited, stopping")
                    break
                response.raise_for_status()
                data = response.json()

                papers = data.get('data', [])
                if not papers:
                    break

                for paper in papers:
                    if paper.get('abstract'):  # Skip papers without abstracts
                        results.append(paper)

                total = data.get('total', 0)
                offset += limit
                if offset >= total:
                    break

            except Exception as e:
                logger.error(f"Semantic Scholar search error for '{disease_term}': {e}")
                break

        logger.info(f"Found {len(results)} papers for '{disease_term}' from Semantic Scholar")
        return results

    async def fetch_details(self, external_id: str) -> Dict[str, Any]:
        return {}

    def extract_document_data(self, raw_data: Dict[str, Any]) -> Tuple[DocumentCreate, Optional[datetime]]:
        paper_id = raw_data.get('paperId', '')
        title = raw_data.get('title', 'Untitled')
        abstract = raw_data.get('abstract', '')
        
        # Build author list
        authors = [a.get('name', '') for a in raw_data.get('authors', []) if a.get('name')]
        
        # Parse date
        source_updated_at = None
        pub_date = raw_data.get('publicationDate')
        if pub_date:
            try:
                source_updated_at = datetime.strptime(pub_date, "%Y-%m-%d")
            except (ValueError, TypeError):
                pass
        if not source_updated_at and raw_data.get('year'):
            try:
                source_updated_at = datetime(int(raw_data['year']), 1, 1)
            except (ValueError, TypeError):
                pass

        # External IDs
        ext_ids = raw_data.get('externalIds') or {}
        doi = ext_ids.get('DOI', '')
        
        # Journal
        journal = raw_data.get('journal', {})
        journal_name = journal.get('name', '') if isinstance(journal, dict) else ''

        metadata = {
            'authors': authors,
            'year': raw_data.get('year'),
            'citation_count': raw_data.get('citationCount', 0),
            'journal': journal_name,
            'doi': doi,
            'arxiv_id': ext_ids.get('ArXiv', ''),
            'pmid': ext_ids.get('PubMed', ''),
            'publication_date': pub_date,
            'semantic_scholar_id': paper_id,
        }

        url = raw_data.get('url', '')
        if doi and not url:
            url = f"https://doi.org/{doi}"

        return DocumentCreate(
            source_id=self.source_id,
            external_id=f"s2_{paper_id}",
            url=url,
            title=title,
            content=abstract,
            summary=abstract[:500] if abstract else title,
            metadata=metadata
        ), source_updated_at
