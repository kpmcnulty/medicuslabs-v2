from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime
from loguru import logger
from urllib.parse import quote_plus

from .base import BaseScraper
from models.schemas import DocumentCreate


class OpenFDAScraper(BaseScraper):
    """Scraper for OpenFDA Drug Labels with cursor-based resume"""

    def __init__(self, source_id: int = None):
        super().__init__(
            source_id=source_id or 0,
            source_name="OpenFDA",
            rate_limit=4.0
        )
        self.base_url = "https://api.fda.gov/drug/label.json"

    async def search(self, disease_term: str, **kwargs) -> List[Dict[str, Any]]:
        """Search OpenFDA with cursor-based pagination"""
        if not disease_term:
            return []

        max_results = kwargs.get('max_results')  # None = unlimited

        # Load cursor
        cursor = await self.get_cursor(disease_term)
        saved_skip = cursor.get('skip', 0)
        exhausted = cursor.get('exhausted', False)

        if exhausted:
            logger.info(f"OpenFDA: Exhausted for '{disease_term}', re-checking")
            saved_skip = 0

        logger.info(f"Searching OpenFDA for: {disease_term} (skip {saved_skip})")

        search_query = f"indications_and_usage:{disease_term}"
        page_size = 100  # OpenFDA max
        all_results = []
        skip = saved_skip

        try:
            while max_results is None or len(all_results) < max_results:
                params = {
                    'search': search_query,
                    'limit': page_size,
                    'skip': skip
                }

                try:
                    data = await self.make_request(self.base_url, params=params)
                    results = data.get('results', [])
                    if not results:
                        await self.mark_exhausted(disease_term)
                        break

                    all_results.extend(results)

                    meta = data.get('meta', {})
                    total = meta.get('results', {}).get('total', 0)
                    skip += page_size

                    # Save cursor after each page
                    await self.save_cursor(disease_term, skip=skip)

                    if skip >= total or skip >= 26000:  # OpenFDA skip limit
                        await self.mark_exhausted(disease_term)
                        break

                except Exception as e:
                    logger.error(f"Error searching OpenFDA at skip {skip}: {e}")
                    await self.save_cursor(disease_term, skip=skip)
                    break

        except Exception as e:
            logger.error(f"Error searching OpenFDA for '{disease_term}': {e}")

        if max_results:
            all_results = all_results[:max_results]
        logger.info(f"Found {len(all_results)} drug labels for '{disease_term}'")
        return all_results

    async def fetch_details(self, external_id: str) -> Dict[str, Any]:
        return {}

    def extract_document_data(self, raw_data: Dict[str, Any]) -> Tuple[DocumentCreate, Optional[datetime]]:
        external_id = raw_data.get('set_id', [None])[0] or raw_data.get('application_number', [None])[0] or ''

        brand_name = ', '.join(raw_data.get('openfda', {}).get('brand_name', [])) or ''
        generic_name = ', '.join(raw_data.get('openfda', {}).get('generic_name', [])) or ''

        if brand_name and generic_name:
            title = f"{brand_name} ({generic_name})"
        elif brand_name:
            title = brand_name
        elif generic_name:
            title = generic_name
        else:
            title = "Unknown Drug"

        indications = '\n\n'.join(raw_data.get('indications_and_usage', []))
        warnings = '\n\n'.join(raw_data.get('warnings', []))
        adverse_reactions = '\n\n'.join(raw_data.get('adverse_reactions', []))

        content_parts = []
        if indications:
            content_parts.append(f"INDICATIONS AND USAGE:\n{indications}")
        if warnings:
            content_parts.append(f"WARNINGS:\n{warnings}")
        if adverse_reactions:
            content_parts.append(f"ADVERSE REACTIONS:\n{adverse_reactions}")

        content = '\n\n---\n\n'.join(content_parts)
        summary = content[:500] if len(content) > 500 else content

        metadata = {
            'brand_name': brand_name, 'generic_name': generic_name,
            'manufacturer': ', '.join(raw_data.get('openfda', {}).get('manufacturer_name', [])),
            'dosage_and_administration': '\n\n'.join(raw_data.get('dosage_and_administration', [])),
            'drug_interactions': '\n\n'.join(raw_data.get('drug_interactions', [])),
            'application_number': ', '.join(raw_data.get('application_number', [])),
            'product_type': ', '.join(raw_data.get('openfda', {}).get('product_type', [])),
            'route': ', '.join(raw_data.get('openfda', {}).get('route', [])),
        }

        url = f"https://www.accessdata.fda.gov/scripts/cder/daf/"
        if external_id:
            url = f"https://dailymed.nlm.nih.gov/dailymed/drugInfo.cfm?setid={external_id}"

        return DocumentCreate(
            source_id=self.source_id,
            external_id=f"openfda_{external_id}",
            url=url, title=title,
            content=content, summary=summary, metadata=metadata
        ), None
