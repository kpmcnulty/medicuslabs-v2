from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime
from loguru import logger
from urllib.parse import quote_plus

from .base import BaseScraper
from models.schemas import DocumentCreate


class OpenFDAScraper(BaseScraper):
    """Scraper for OpenFDA Drug Labels"""

    def __init__(self, source_id: int = None):
        super().__init__(
            source_id=source_id or 0,
            source_name="OpenFDA",
            rate_limit=4.0  # 4 requests per second (240/min without API key)
        )
        self.base_url = "https://api.fda.gov/drug/label.json"

    async def search(self, disease_term: str, **kwargs) -> List[Dict[str, Any]]:
        """Search OpenFDA for drug labels related to a disease"""
        if not disease_term:
            logger.warning("No disease term provided for OpenFDA search")
            return []

        logger.info(f"Searching OpenFDA for: {disease_term}")

        try:
            # Build search query for indications_and_usage field
            search_query = f"indications_and_usage:{disease_term}"

            params = {
                'search': search_query,
                'limit': kwargs.get('max_results', 20)
            }

            data = await self.make_request(self.base_url, params=params)

            results = data.get('results', [])
            logger.info(f"Found {len(results)} drug labels for '{disease_term}'")
            return results

        except Exception as e:
            logger.error(f"Error searching OpenFDA for '{disease_term}': {e}")
            return []

    async def fetch_details(self, external_id: str) -> Dict[str, Any]:
        """OpenFDA API returns all data in search - no detail fetching needed"""
        return {}

    def extract_document_data(self, raw_data: Dict[str, Any]) -> Tuple[DocumentCreate, Optional[datetime]]:
        """Extract and transform OpenFDA drug label data"""

        # Use set_id or application_number as unique identifier
        external_id = raw_data.get('set_id', [None])[0] or raw_data.get('application_number', [None])[0] or ''

        # Extract drug names
        brand_name = ', '.join(raw_data.get('openfda', {}).get('brand_name', [])) or ''
        generic_name = ', '.join(raw_data.get('openfda', {}).get('generic_name', [])) or ''

        # Build title
        if brand_name and generic_name:
            title = f"{brand_name} ({generic_name})"
        elif brand_name:
            title = brand_name
        elif generic_name:
            title = generic_name
        else:
            title = "Unknown Drug"

        # Extract key sections for content
        indications = '\n\n'.join(raw_data.get('indications_and_usage', []))
        warnings = '\n\n'.join(raw_data.get('warnings', []))
        adverse_reactions = '\n\n'.join(raw_data.get('adverse_reactions', []))

        # Combine into content
        content_parts = []
        if indications:
            content_parts.append(f"INDICATIONS AND USAGE:\n{indications}")
        if warnings:
            content_parts.append(f"WARNINGS:\n{warnings}")
        if adverse_reactions:
            content_parts.append(f"ADVERSE REACTIONS:\n{adverse_reactions}")

        content = '\n\n---\n\n'.join(content_parts)
        summary = content[:500] if len(content) > 500 else content

        # Extract metadata
        metadata = {
            'brand_name': brand_name,
            'generic_name': generic_name,
            'manufacturer': ', '.join(raw_data.get('openfda', {}).get('manufacturer_name', [])),
            'dosage_and_administration': '\n\n'.join(raw_data.get('dosage_and_administration', [])),
            'drug_interactions': '\n\n'.join(raw_data.get('drug_interactions', [])),
            'application_number': ', '.join(raw_data.get('application_number', [])),
            'product_type': ', '.join(raw_data.get('openfda', {}).get('product_type', [])),
            'route': ', '.join(raw_data.get('openfda', {}).get('route', [])),
        }

        # No source_updated_at since FDA doesn't provide last modified dates easily
        source_updated_at = None

        # Build URL to drug label (if we have application number)
        url = f"https://www.accessdata.fda.gov/scripts/cder/daf/"
        if external_id:
            url = f"https://dailymed.nlm.nih.gov/dailymed/drugInfo.cfm?setid={external_id}"

        return DocumentCreate(
            source_id=self.source_id,
            external_id=f"openfda_{external_id}",
            url=url,
            title=title,
            content=content,
            summary=summary,
            metadata=metadata
        ), source_updated_at
