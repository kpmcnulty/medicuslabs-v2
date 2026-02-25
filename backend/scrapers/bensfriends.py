"""Ben's Friends Discourse forum scraper.
Ben's Friends runs rare disease community forums on Discourse.
Uses the public Discourse JSON API to fetch posts and topics.
"""
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime
from loguru import logger
from urllib.parse import quote_plus

from .base import BaseScraper
from models.schemas import DocumentCreate


# Ben's Friends Discourse sites with public APIs
BENSFRIENDS_SITES = [
    {"slug": "rarediseases", "url": "https://rarediseases.bensfriends.org", "name": "Rare Diseases Hub"},
]

# Additional community Discourse sites (tested for API access)
DISCOURSE_COMMUNITIES = [
    # Add more Discourse-based health forums here as they're discovered
]


class BensFriendsScraper(BaseScraper):
    """Scraper for Ben's Friends Discourse community forums"""

    def __init__(self, source_id: int = None):
        super().__init__(
            source_id=source_id or 0,
            source_name="Ben's Friends",
            rate_limit=1.0  # Be respectful
        )

    async def search(self, disease_term: str, **kwargs) -> List[Dict[str, Any]]:
        """Search Ben's Friends Discourse forums for disease-related topics"""
        if not disease_term:
            return []

        max_results = kwargs.get('max_results')
        logger.info(f"Searching Ben's Friends for: {disease_term}")

        results = []

        for site in BENSFRIENDS_SITES:
            try:
                # Search the Discourse API
                site_results = await self._search_discourse(
                    site['url'], site['name'], disease_term, max_results
                )
                results.extend(site_results)
            except Exception as e:
                logger.warning(f"Error searching {site['name']}: {e}")

        # Also fetch latest/top topics from each site (not just search matches)
        for site in BENSFRIENDS_SITES:
            try:
                latest = await self._fetch_latest_topics(
                    site['url'], site['name'], max_results=50
                )
                # Add topics we haven't seen
                seen_ids = {r.get('topic_id') for r in results}
                for topic in latest:
                    if topic.get('topic_id') not in seen_ids:
                        results.append(topic)
            except Exception as e:
                logger.debug(f"Error fetching latest from {site['name']}: {e}")

        logger.info(f"Found {len(results)} topics from Ben's Friends for '{disease_term}'")
        return results[:max_results]

    async def _search_discourse(self, base_url: str, site_name: str,
                                 query: str, max_results: int) -> List[Dict[str, Any]]:
        """Search a Discourse forum via its JSON API"""
        results = []
        try:
            await self.rate_limiter.acquire()
            response = await self.client.get(
                f"{base_url}/search.json",
                params={'q': query},
                headers={'Accept': 'application/json'},
                timeout=15
            )
            if response.status_code != 200:
                logger.debug(f"Discourse search returned {response.status_code} for {base_url}")
                return []

            data = response.json()
            topics = {t['id']: t for t in data.get('topics', [])}
            posts = data.get('posts', [])

            for post in posts[:max_results]:
                topic_id = post.get('topic_id')
                topic = topics.get(topic_id, {})

                # Fetch full topic with replies
                full_topic = await self._fetch_topic(base_url, topic_id)

                results.append({
                    'topic_id': topic_id,
                    'post_id': post.get('id'),
                    'title': topic.get('title', post.get('topic_slug', '')),
                    'content': post.get('blurb', ''),
                    'full_content': full_topic.get('content', '') if full_topic else '',
                    'author': post.get('username', 'anonymous'),
                    'created_at': post.get('created_at', ''),
                    'reply_count': topic.get('reply_count', 0) or topic.get('posts_count', 1) - 1,
                    'views': topic.get('views', 0),
                    'like_count': post.get('like_count', 0),
                    'site_name': site_name,
                    'site_url': base_url,
                    'url': f"{base_url}/t/{topic.get('slug', 'topic')}/{topic_id}",
                    'replies': full_topic.get('replies', []) if full_topic else [],
                    'tags': topic.get('tags', []),
                    'category': full_topic.get('category', '') if full_topic else '',
                })

        except Exception as e:
            logger.warning(f"Error searching Discourse at {base_url}: {e}")

        return results

    async def _fetch_topic(self, base_url: str, topic_id: int) -> Optional[Dict[str, Any]]:
        """Fetch full topic with posts from Discourse"""
        if not topic_id:
            return None
        try:
            await self.rate_limiter.acquire()
            response = await self.client.get(
                f"{base_url}/t/{topic_id}.json",
                headers={'Accept': 'application/json'},
                timeout=15
            )
            if response.status_code != 200:
                return None

            data = response.json()
            posts = data.get('post_stream', {}).get('posts', [])
            category_id = data.get('category_id')

            content = ''
            replies = []

            for i, post in enumerate(posts[:20]):  # Limit to 20 posts per topic
                post_content = post.get('cooked', '')  # HTML content
                # Strip HTML tags for plain text
                import re
                plain_text = re.sub(r'<[^>]+>', ' ', post_content).strip()
                plain_text = re.sub(r'\s+', ' ', plain_text)

                if i == 0:
                    content = plain_text
                else:
                    replies.append({
                        'author': post.get('username', 'anonymous'),
                        'content': plain_text[:2000],
                        'created_at': post.get('created_at', ''),
                        'like_count': post.get('like_count', 0),
                    })

            return {
                'content': content,
                'replies': replies,
                'category': str(category_id) if category_id else '',
            }

        except Exception as e:
            logger.debug(f"Error fetching topic {topic_id}: {e}")
            return None

    async def _fetch_latest_topics(self, base_url: str, site_name: str,
                                    max_results: int = 300) -> List[Dict[str, Any]]:
        """Fetch latest topics from a Discourse forum with pagination"""
        results = []
        page = 0

        try:
            while max_results is None or len(results) < max_results:
                await self.rate_limiter.acquire()
                response = await self.client.get(
                    f"{base_url}/latest.json",
                    params={'page': page},
                    headers={'Accept': 'application/json'},
                    timeout=15
                )
                if response.status_code != 200:
                    break

                data = response.json()
                topics = data.get('topic_list', {}).get('topics', [])
                
                if not topics:
                    break
                    
                more = data.get('topic_list', {}).get('more_topics_url', '')
                logger.info(f"Ben's Friends page {page}: {len(topics)} topics ({len(results)} so far)")

                for topic in topics:
                    topic_id = topic.get('id')
                    full_topic = await self._fetch_topic(base_url, topic_id)

                    results.append({
                        'topic_id': topic_id,
                        'post_id': None,
                        'title': topic.get('title', ''),
                        'content': topic.get('excerpt', ''),
                        'full_content': full_topic.get('content', '') if full_topic else '',
                        'author': topic.get('last_poster_username', 'anonymous'),
                        'created_at': topic.get('created_at', ''),
                        'reply_count': topic.get('reply_count', 0),
                        'views': topic.get('views', 0),
                        'like_count': topic.get('like_count', 0),
                        'site_name': site_name,
                        'site_url': base_url,
                        'url': f"{base_url}/t/{topic.get('slug', 'topic')}/{topic_id}",
                        'replies': full_topic.get('replies', []) if full_topic else [],
                        'tags': topic.get('tags', []),
                        'category': full_topic.get('category', '') if full_topic else '',
                    })

                    if max_results is not None and len(results) >= max_results:
                        break

                page += 1
                if not more:
                    break

        except Exception as e:
            logger.warning(f"Error fetching latest from {base_url}: {e}")

        return results

    async def fetch_details(self, topic_id: str) -> Dict[str, Any]:
        return {}

    def extract_document_data(self, raw_data: Dict[str, Any]) -> Tuple[DocumentCreate, Optional[datetime]]:
        topic_id = raw_data.get('topic_id', '')

        content_parts = []
        if raw_data.get('title'):
            content_parts.append(f"TITLE: {raw_data['title']}")
        
        # Use full content if available, else blurb
        main_content = raw_data.get('full_content') or raw_data.get('content', '')
        if main_content:
            content_parts.append(f"CONTENT: {main_content}")

        if raw_data.get('author'):
            content_parts.append(f"AUTHOR: {raw_data['author']}")
        if raw_data.get('site_name'):
            content_parts.append(f"COMMUNITY: {raw_data['site_name']}")
        if raw_data.get('tags'):
            content_parts.append(f"TAGS: {', '.join(raw_data['tags'])}")

        content_parts.append(f"VIEWS: {raw_data.get('views', 0)} | REPLIES: {raw_data.get('reply_count', 0)}")

        if raw_data.get('replies'):
            content_parts.append("\nREPLIES:")
            for i, reply in enumerate(raw_data['replies'][:10], 1):
                content_parts.append(f"\n{i}. {reply.get('author', 'anonymous')}:")
                content_parts.append(f"   {reply.get('content', '')[:1000]}")

        content = "\n\n".join(content_parts)

        summary = raw_data.get('title', '')
        if main_content:
            summary += f" - {main_content[:200]}"
        summary = summary[:500]

        source_updated_at = None
        posted_date = None
        if raw_data.get('created_at'):
            try:
                date_str = raw_data['created_at'].split('.')[0].replace('Z', '')
                source_updated_at = datetime.fromisoformat(date_str)
                posted_date = source_updated_at.isoformat()
            except:
                pass

        metadata = {
            'topic_id': str(topic_id),
            'community': raw_data.get('site_name', "Ben's Friends"),
            'author': raw_data.get('author', 'anonymous'),
            'reply_count': raw_data.get('reply_count', 0),
            'views': raw_data.get('views', 0),
            'posted_date': posted_date,
            'tags': raw_data.get('tags', []),
        }

        return DocumentCreate(
            source_id=self.source_id,
            external_id=f"bensfriends_{topic_id}",
            url=raw_data.get('url', ''),
            title=raw_data.get('title', 'Untitled'),
            content=content,
            summary=summary,
            metadata=metadata
        ), source_updated_at
