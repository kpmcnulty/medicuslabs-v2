from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime
from loguru import logger

from .base import BaseScraper
from models.schemas import DocumentCreate


class PatientInfoScraper(BaseScraper):
    """Scraper for Patient.info community forums (Discourse-based) with cursor-based resume"""

    def __init__(self, source_id: int = None):
        super().__init__(
            source_id=source_id or 0,
            source_name="Patient.info Forums",
            rate_limit=1.0
        )
        self.base_url = "https://community.patient.info"

    async def search(self, disease_term: str, **kwargs) -> List[Dict[str, Any]]:
        if not disease_term:
            return []

        max_results = kwargs.get('max_results')  # None = unlimited

        # Load cursor
        cursor = await self.get_cursor(disease_term)
        saved_page = cursor.get('page', 1)
        exhausted = cursor.get('exhausted', False)

        if exhausted:
            logger.info(f"Patient.info: Exhausted for '{disease_term}', running incremental")
            saved_page = 1

        results = []
        page = saved_page

        while max_results is None or len(results) < max_results:
            params = {'q': disease_term, 'page': page}
            try:
                data = await self.make_request(f"{self.base_url}/search.json", params=params)
                topics = data.get('topics', [])
                posts = data.get('posts', [])

                if not topics:
                    await self.mark_exhausted(disease_term)
                    break

                post_by_topic = {}
                for p in posts:
                    tid = p.get('topic_id')
                    if tid not in post_by_topic:
                        post_by_topic[tid] = p

                for topic in topics:
                    topic_id = topic.get('id')
                    if topic_id in post_by_topic:
                        topic['first_post'] = post_by_topic[topic_id]
                    results.append(topic)

                grouped = data.get('grouped_search_result', {})
                if not grouped.get('more_full_page_results'):
                    await self.mark_exhausted(disease_term)
                    break

                page += 1
                # Save cursor after each page
                await self.save_cursor(disease_term, page=page)

            except Exception as e:
                logger.error(f"Patient.info search error: {e}")
                await self.save_cursor(disease_term, page=page)
                break

        logger.info(f"Found {len(results)} topics on Patient.info for '{disease_term}'")
        if max_results:
            return results[:max_results]
        return results

    async def fetch_details(self, external_id: str) -> Dict[str, Any]:
        return {}

    def extract_document_data(self, raw_data: Dict[str, Any]) -> Tuple[DocumentCreate, Optional[datetime]]:
        topic_id = raw_data.get('id', '')
        title = raw_data.get('title', 'Untitled')
        slug = raw_data.get('slug', '')
        posts_count = raw_data.get('posts_count', 0)

        first_post = raw_data.get('first_post', {})
        blurb = first_post.get('blurb', '')
        author = first_post.get('username', 'anonymous')

        tags = [t.get('name', '') for t in raw_data.get('tags', []) if isinstance(t, dict)]

        parts = [f"TOPIC: {title}"]
        if tags:
            parts.append(f"Tags: {', '.join(tags)}")
        if blurb:
            parts.append(f"POST: {blurb}")
        parts.append(f"Replies: {posts_count - 1} | Views: N/A")

        content = "\n\n".join(parts)
        summary = f"{title[:300]}"

        source_updated_at = None
        posted_date = None
        created = raw_data.get('created_at') or (first_post.get('created_at') if first_post else None)
        if created:
            try:
                source_updated_at = datetime.fromisoformat(created.replace('Z', '+00:00')).replace(tzinfo=None)
                posted_date = source_updated_at.strftime("%Y-%m-%d")
            except:
                pass

        bumped = raw_data.get('bumped_at')
        if bumped:
            try:
                bumped_dt = datetime.fromisoformat(bumped.replace('Z', '+00:00')).replace(tzinfo=None)
                if not source_updated_at or bumped_dt > source_updated_at:
                    source_updated_at = bumped_dt
            except:
                pass

        url = f"{self.base_url}/t/{slug}/{topic_id}"

        metadata = {
            'community': 'Patient.info', 'author': author,
            'reply_count': max(0, posts_count - 1),
            'posted_date': posted_date, 'tags': tags,
        }

        return DocumentCreate(
            source_id=self.source_id,
            external_id=f"patientinfo_{topic_id}",
            url=url, title=title[:500],
            content=content, summary=summary[:500],
            metadata=metadata
        ), source_updated_at
