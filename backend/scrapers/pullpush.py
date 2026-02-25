from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime
from loguru import logger
import time

from .base import BaseScraper
from models.schemas import DocumentCreate


class PullpushScraper(BaseScraper):
    """Scraper for Reddit historical data via Pullpush.io (formerly Pushshift)"""

    def __init__(self, source_id: int = None):
        super().__init__(
            source_id=source_id or 0,
            source_name="Pullpush Reddit",
            rate_limit=1.0  # ~1 req/sec
        )
        self.base_url = "https://api.pullpush.io/reddit"

    async def search(self, disease_term: str, **kwargs) -> List[Dict[str, Any]]:
        """Search Reddit historical data for disease-related submissions.
        
        Supports incremental scraping via crawl_state:
        - Stores last_timestamp per disease_term
        - Incremental: only fetches posts newer than last run
        - Historical: paginates backwards through all time
        """
        if not disease_term:
            return []

        max_results = kwargs.get('max_results') or 5000
        before = kwargs.get('before')  # epoch timestamp
        after = kwargs.get('after')    # epoch timestamp
        
        # Check crawl state for incremental support
        if not after and not before:
            try:
                state = await self.get_source_state()
                crawl_state = state.get('crawl_state', {})
                if isinstance(crawl_state, str):
                    import json
                    crawl_state = json.loads(crawl_state)
                disease_key = disease_term.lower().replace(' ', '_')
                last_ts = crawl_state.get(f'last_timestamp_{disease_key}')
                if last_ts:
                    after = int(last_ts)
                    logger.info(f"Incremental mode: fetching posts after {datetime.fromtimestamp(after)}")
            except Exception as e:
                logger.debug(f"Could not load crawl state: {e}")

        results = []
        current_before = before  # None means latest

        while len(results) < max_results:
            batch_size = min(100, max_results - len(results))
            params = {
                'q': disease_term,
                'size': batch_size,
            }
            if current_before:
                params['before'] = int(current_before)
            if after:
                params['after'] = int(after)

            try:
                data = await self.make_request(f"{self.base_url}/search/submission", params=params)
                items = data.get('data', [])
                if not items:
                    break

                # Filter out low-quality posts
                for item in items:
                    if item.get('selftext') in ('[removed]', '[deleted]', ''):
                        item['selftext'] = ''
                    # Keep posts with title at minimum
                    if item.get('title'):
                        results.append(item)

                # Paginate: use oldest item's timestamp as next before
                oldest_ts = min(item.get('created_utc', 0) for item in items)
                if oldest_ts and oldest_ts == current_before:
                    break  # No progress
                current_before = oldest_ts

                if len(items) < batch_size:
                    break  # No more data

            except Exception as e:
                logger.error(f"Pullpush submission search error: {e}")
                break

        # Fetch top comments for a subset (rate limit is strict on comments endpoint)
        comment_limit = min(10, len(results))
        if comment_limit > 0:
            await self._fetch_comments_batch(results[:comment_limit])

        # Update crawl state with newest timestamp for incremental next time
        if results:
            try:
                newest_ts = max(r.get('created_utc', 0) for r in results)
                if newest_ts:
                    disease_key = disease_term.lower().replace(' ', '_')
                    state = await self.get_source_state()
                    crawl_state = state.get('crawl_state', {})
                    if isinstance(crawl_state, str):
                        import json
                        crawl_state = json.loads(crawl_state)
                    crawl_state[f'last_timestamp_{disease_key}'] = newest_ts
                    await self.update_source_state(crawl_state=crawl_state)
            except Exception as e:
                logger.debug(f"Could not save crawl state: {e}")

        logger.info(f"Found {len(results)} Reddit submissions for '{disease_term}'")
        return results[:max_results]

    async def _fetch_comments_batch(self, submissions: List[Dict]):
        """Fetch top comments for submissions via comment search"""
        for sub in submissions:
            try:
                params = {
                    'link_id': sub['id'],
                    'size': 5,
                    'sort': 'desc',
                    'sort_type': 'score',
                }
                data = await self.make_request(f"{self.base_url}/search/comment", params=params)
                comments = data.get('data', [])
                sub['top_comments'] = [
                    {
                        'author': c.get('author', '[deleted]'),
                        'body': c.get('body', '')[:500],
                        'score': c.get('score', 0),
                    }
                    for c in comments
                    if c.get('body') not in ('[removed]', '[deleted]', '')
                ]
            except Exception as e:
                logger.debug(f"Failed to fetch comments for {sub['id']}: {e}")
                sub['top_comments'] = []

    async def fetch_details(self, external_id: str) -> Dict[str, Any]:
        """Not needed - details fetched in search"""
        return {}

    def extract_document_data(self, raw_data: Dict[str, Any]) -> Tuple[DocumentCreate, Optional[datetime]]:
        """Transform Reddit submission data into DocumentCreate"""
        submission_id = raw_data.get('id', '')
        subreddit = raw_data.get('subreddit', 'unknown')
        author = raw_data.get('author', '[deleted]')
        title = raw_data.get('title', 'Untitled')
        selftext = raw_data.get('selftext', '')
        score = raw_data.get('score', 0)
        num_comments = raw_data.get('num_comments', 0)
        created_utc = raw_data.get('created_utc', 0)

        # Build content
        parts = [f"TITLE: {title}"]
        if selftext:
            parts.append(f"POST: {selftext[:3000]}")
        parts.append(f"Subreddit: r/{subreddit} | Score: {score} | Comments: {num_comments}")

        # Add top comments
        top_comments = raw_data.get('top_comments', [])
        if top_comments:
            parts.append("\nTOP COMMENTS:")
            for c in top_comments[:3]:
                parts.append(f"  [{c.get('score', 0)} pts] u/{c.get('author', '?')}: {c.get('body', '')}")

        content = "\n\n".join(parts)
        summary = f"{title[:200]} - r/{subreddit}"

        # Parse timestamp
        source_updated_at = None
        posted_date = None
        if created_utc:
            try:
                source_updated_at = datetime.fromtimestamp(created_utc)
                posted_date = source_updated_at.strftime("%Y-%m-%d")
            except:
                pass

        url = raw_data.get('url', f"https://reddit.com/r/{subreddit}/comments/{submission_id}")
        permalink = raw_data.get('permalink', '')
        if permalink:
            url = f"https://reddit.com{permalink}"

        metadata = {
            'community': f"r/{subreddit}",
            'author': author,
            'reply_count': num_comments,
            'posted_date': posted_date,
            'score': score,
            'subreddit': subreddit,
        }

        return DocumentCreate(
            source_id=self.source_id,
            external_id=f"reddit_{submission_id}",
            url=url,
            title=title[:500],
            content=content,
            summary=summary[:500],
            metadata=metadata
        ), source_updated_at
