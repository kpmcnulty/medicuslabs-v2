from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime
from loguru import logger
from urllib.parse import quote_plus

from .base import BaseScraper
from models.schemas import DocumentCreate


class HealthUnlockedScraper(BaseScraper):
    """Scraper for HealthUnlocked community posts via their public JSON API"""

    def __init__(self, source_id: int = None):
        super().__init__(
            source_id=source_id or 0,
            source_name="HealthUnlocked",
            rate_limit=0.5
        )
        self.base_url = "https://healthunlocked.com"
        self.api_url = "https://healthunlocked.com/public/search/posts"

    async def search(self, disease_term: str, **kwargs) -> List[Dict[str, Any]]:
        """Search HealthUnlocked via their public search API with pagination"""
        if not disease_term:
            return []

        max_results = kwargs.get('max_results')
        fetch_full = kwargs.get('fetch_full_posts', True)
        
        # Load cursor for resume
        disease_key = disease_term.lower().replace(' ', '_').replace('-', '_')
        offset = 0
        try:
            state = await self.get_source_state()
            crawl_state = state.get('crawl_state', {})
            if isinstance(crawl_state, str):
                import json as _json
                crawl_state = _json.loads(crawl_state)
            saved_offset = crawl_state.get(f'{disease_key}_offset', 0)
            if saved_offset > 0:
                offset = saved_offset
                logger.info(f"HealthUnlocked: Resuming '{disease_term}' from offset {offset}")
        except Exception:
            pass

        logger.info(f"Searching HealthUnlocked API for: {disease_term} (offset {offset}, max {max_results})")

        results = []
        page_size = 20

        try:
            while max_results is None or len(results) < max_results:
                await self.rate_limiter.acquire()
                params = {'q': disease_term}
                if offset > 0:
                    params['start'] = offset

                response = await self.client.get(
                    self.api_url,
                    params=params,
                    headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
                )
                response.raise_for_status()
                data = response.json()

                posts = data.get('posts', [])
                total = data.get('total', 0)

                if not posts:
                    break

                logger.info(f"HealthUnlocked page {offset // page_size + 1}: "
                           f"{len(posts)} posts ({len(results)}/{min(total, max_results)} so far)")

                for post in posts:
                    if max_results is not None and len(results) >= max_results:
                        break

                    post_id = post.get('postId')
                    community = post.get('community', {})
                    author = post.get('author', {})
                    highlight = post.get('highlight', [])

                    # Build content from highlights
                    content = '\n'.join(highlight).replace('[b]', '').replace('[/b]', '').replace('[i]', '').replace('[/i]', '')

                    # Fetch full post content (rate limited)
                    if fetch_full:
                        full_content = await self._fetch_post(community.get('slug', ''), post_id)
                        if full_content:
                            content = full_content

                    results.append({
                        'post_id': str(post_id),
                        'title': post.get('title', 'Untitled'),
                        'content': content,
                        'author': author.get('username', 'Anonymous'),
                        'community': community.get('name', ''),
                        'community_slug': community.get('slug', ''),
                        'date': post.get('dateCreated'),
                        'reply_count': post.get('totalResponses', 0),
                        'link': f"{self.base_url}/{community.get('slug', '')}/posts/{post_id}" if community.get('slug') else '',
                    })

                offset += page_size

                # Save cursor so we can resume if interrupted
                try:
                    state = await self.get_source_state()
                    crawl_state = state.get('crawl_state', {})
                    if isinstance(crawl_state, str):
                        import json as _json
                        crawl_state = _json.loads(crawl_state)
                    crawl_state[f'{disease_key}_offset'] = offset
                    if offset >= total:
                        crawl_state[f'{disease_key}_exhausted'] = True
                    await self.update_source_state(crawl_state=crawl_state)
                except Exception:
                    pass

                # Stop if we've fetched all available
                if offset >= total:
                    logger.info(f"HealthUnlocked: Exhausted all {total} posts for '{disease_term}'")
                    break

            logger.info(f"Found {len(results)} posts on HealthUnlocked for '{disease_term}'")
            return results

        except Exception as e:
            logger.error(f"Error searching HealthUnlocked for '{disease_term}': {e}")
            return results  # Return what we have so far

    async def _fetch_post(self, community_slug: str, post_id: int) -> Optional[str]:
        """Fetch full post content via API"""
        if not community_slug or not post_id:
            return None
        try:
            await self.rate_limiter.acquire()
            response = await self.client.get(
                f"{self.base_url}/public/{community_slug}/posts/{post_id}",
                headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
            )
            if response.status_code == 200:
                data = response.json()
                post_body = data.get('body', '') or data.get('content', '') or data.get('text', '')
                responses = data.get('responses', [])
                parts = [post_body] if post_body else []
                for r in responses[:10]:
                    reply_text = r.get('body', '') or r.get('text', '')
                    reply_author = r.get('author', {}).get('username', 'Anonymous')
                    if reply_text:
                        parts.append(f"\nREPLY by {reply_author}:\n{reply_text}")
                return '\n'.join(parts) if parts else None
        except Exception as e:
            logger.debug(f"Could not fetch full post {post_id}: {e}")
        return None

    async def fetch_details(self, post_id: str) -> Dict[str, Any]:
        return {}

    def extract_document_data(self, raw_data: Dict[str, Any]) -> Tuple[DocumentCreate, Optional[datetime]]:
        post_id = raw_data.get('post_id', '')

        content_parts = []
        if raw_data.get('title'):
            content_parts.append(f"TITLE: {raw_data['title']}")
        if raw_data.get('content'):
            content_parts.append(f"CONTENT: {raw_data['content']}")
        if raw_data.get('author'):
            content_parts.append(f"AUTHOR: {raw_data['author']}")
        if raw_data.get('community'):
            content_parts.append(f"COMMUNITY: {raw_data['community']}")
        content_parts.append(f"REPLIES: {raw_data.get('reply_count', 0)}")

        content = "\n\n".join(content_parts)

        summary = raw_data.get('title', '')
        if raw_data.get('content'):
            summary += f" - {raw_data['content'][:200]}"
        summary = summary[:500]

        source_updated_at = None
        posted_date = None
        if raw_data.get('date'):
            try:
                date_str = raw_data['date'].split('.')[0].split('+')[0].replace('Z', '')
                source_updated_at = datetime.fromisoformat(date_str)
                posted_date = source_updated_at.strftime("%Y-%m-%d")
            except:
                pass

        metadata = {
            'post_id': post_id,
            'community': raw_data.get('community', ''),
            'community_slug': raw_data.get('community_slug', ''),
            'author': raw_data.get('author', 'Anonymous'),
            'reply_count': raw_data.get('reply_count', 0),
            'posted_date': posted_date,
        }

        return DocumentCreate(
            source_id=self.source_id,
            external_id=f"healthunlocked_{post_id}",
            url=raw_data.get('link', ''),
            title=raw_data.get('title', 'Untitled Post'),
            content=content,
            summary=summary,
            metadata=metadata
        ), source_updated_at
