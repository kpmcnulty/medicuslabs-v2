from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime
from loguru import logger

from .base import BaseScraper
from models.schemas import DocumentCreate


class PatientInfoScraper(BaseScraper):
    """Scraper for Patient.info community forums (Discourse-based)"""

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

        max_results = kwargs.get('max_results') or 50
        results = []
        page = 1

        while len(results) < max_results:
            params = {'q': disease_term, 'page': page}
            try:
                data = await self.make_request(f"{self.base_url}/search.json", params=params)
                topics = data.get('topics', [])
                posts = data.get('posts', [])

                if not topics:
                    break

                # Build post lookup by topic
                post_by_topic = {}
                for p in posts:
                    tid = p.get('topic_id')
                    if tid not in post_by_topic:
                        post_by_topic[tid] = p

                for topic in topics:
                    topic_id = topic.get('id')
                    # Merge first matching post content
                    if topic_id in post_by_topic:
                        topic['first_post'] = post_by_topic[topic_id]
                    results.append(topic)

                # Check if more pages
                grouped = data.get('grouped_search_result', {})
                if not grouped.get('more_full_page_results'):
                    break
                page += 1

            except Exception as e:
                logger.error(f"Patient.info search error: {e}")
                break

        logger.info(f"Found {len(results)} topics on Patient.info for '{disease_term}'")
        return results[:max_results]

    async def fetch_details(self, external_id: str) -> Dict[str, Any]:
        return {}

    def extract_document_data(self, raw_data: Dict[str, Any]) -> Tuple[DocumentCreate, Optional[datetime]]:
        topic_id = raw_data.get('id', '')
        title = raw_data.get('title', 'Untitled')
        slug = raw_data.get('slug', '')
        posts_count = raw_data.get('posts_count', 0)
        reply_count = raw_data.get('reply_count', 0)

        # Get first post content
        first_post = raw_data.get('first_post', {})
        blurb = first_post.get('blurb', '')
        author = first_post.get('username', 'anonymous')

        # Tags
        tags = [t.get('name', '') for t in raw_data.get('tags', []) if isinstance(t, dict)]

        # Build content
        parts = [f"TOPIC: {title}"]
        if tags:
            parts.append(f"Tags: {', '.join(tags)}")
        if blurb:
            parts.append(f"POST: {blurb}")
        parts.append(f"Replies: {posts_count - 1} | Views: N/A")

        content = "\n\n".join(parts)
        summary = f"{title[:300]}"

        # Parse dates
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
            'community': 'Patient.info',
            'author': author,
            'reply_count': max(0, posts_count - 1),
            'posted_date': posted_date,
            'tags': tags,
        }

        return DocumentCreate(
            source_id=self.source_id,
            external_id=f"patientinfo_{topic_id}",
            url=url,
            title=title[:500],
            content=content,
            summary=summary[:500],
            metadata=metadata
        ), source_updated_at
