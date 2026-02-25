"""Pullpush Reddit historical scraper.

Strategy:
- First run: paginates backwards from now through ALL of Reddit history
- Saves cursor (oldest_timestamp) per disease after each batch
- Subsequent runs: picks up where it left off, continuing backwards
- Once historical is exhausted, switches to forward/incremental mode
- No artificial caps — gets everything over time
"""
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime
from loguru import logger

from .base import BaseScraper
from models.schemas import DocumentCreate


class PullpushScraper(BaseScraper):
    """Scraper for Reddit historical data via Pullpush.io"""

    def __init__(self, source_id: int = None):
        super().__init__(
            source_id=source_id or 0,
            source_name="Pullpush Reddit",
            rate_limit=1.0
        )
        self.base_url = "https://api.pullpush.io/reddit"

    async def search(self, disease_term: str, **kwargs) -> List[Dict[str, Any]]:
        """Scrape Reddit history for a disease term. Resumes from last cursor."""
        if not disease_term:
            return []

        max_results = kwargs.get('max_results')  # None = unlimited

        # Load cursor state using base class helpers
        cursor = await self.get_cursor(disease_term)
        oldest_seen = cursor.get('oldest_seen')
        newest_seen = cursor.get('newest_seen')
        exhausted = cursor.get('exhausted', False)

        if exhausted:
            # Historical scrape is done — switch to incremental (get new posts)
            logger.info(f"Pullpush: Historical complete for '{disease_term}', running incremental from {datetime.fromtimestamp(newest_seen) if newest_seen else 'now'}")
            results = await self._scrape_incremental(disease_term, newest_seen, max_results)
        else:
            # Historical scrape — paginate backwards from cursor
            logger.info(f"Pullpush: Historical scrape for '{disease_term}', cursor={'from ' + str(datetime.fromtimestamp(oldest_seen)) if oldest_seen else 'start (latest)'}")
            results = await self._scrape_historical(disease_term, oldest_seen, max_results)

        # Update newest_seen for incremental tracking
        if results:
            max_ts = max(r.get('created_utc', 0) for r in results)
            if not newest_seen or max_ts > newest_seen:
                await self.save_cursor(disease_term, newest_seen=max_ts)

        logger.info(f"Pullpush: Got {len(results)} posts for '{disease_term}'")
        return results

    async def _scrape_historical(self, disease_term: str, cursor_before: int = None,
                                  max_results: int = None) -> List[Dict[str, Any]]:
        """Paginate backwards through all history. Saves cursor after each batch."""
        results = []
        current_before = cursor_before
        empty_pages = 0
        batch_num = 0

        while max_results is None or len(results) < max_results:
            batch_num += 1
            params = {
                'q': f'"{disease_term}"',
                'size': 100,
                'sort': 'desc',
            }
            if current_before:
                params['before'] = int(current_before)

            try:
                data = await self.make_request(f"{self.base_url}/search/submission", params=params)
                items = data.get('data', [])

                if not items:
                    empty_pages += 1
                    if empty_pages >= 3:
                        # We've exhausted this source
                        logger.info(f"Pullpush: Historical scrape exhausted for '{disease_term}' after {len(results)} posts")
                        await self.mark_exhausted(disease_term)
                        break
                    continue

                empty_pages = 0

                for item in items:
                    if item.get('selftext') in ('[removed]', '[deleted]'):
                        item['selftext'] = ''
                    if item.get('title'):
                        results.append(item)

                # Move cursor to oldest post in this batch
                oldest_ts = min(item.get('created_utc', 0) for item in items)
                if oldest_ts == current_before:
                    # No progress — we're stuck
                    oldest_ts -= 1
                current_before = oldest_ts

                # Save cursor after every batch so we can resume
                await self.save_cursor(disease_term, oldest_seen=current_before)

                if batch_num % 10 == 0:
                    oldest_date = datetime.fromtimestamp(current_before) if current_before else None
                    logger.info(f"Pullpush: {disease_term} batch {batch_num}, {len(results)} posts so far, cursor at {oldest_date}")

                if len(items) < 100:
                    # Last page
                    logger.info(f"Pullpush: Reached end of history for '{disease_term}'")
                    await self.mark_exhausted(disease_term)
                    break

            except Exception as e:
                logger.error(f"Pullpush error at batch {batch_num}: {e}")
                # Save cursor so we resume from here next time
                if current_before:
                    await self.save_cursor(disease_term, oldest_seen=current_before)
                break

        return results

    async def _scrape_incremental(self, disease_term: str, after_ts: int = None,
                                   max_results: int = None) -> List[Dict[str, Any]]:
        """Get new posts since last scrape."""
        results = []
        params = {
            'q': f'"{disease_term}"',
            'size': 100,
            'sort': 'asc',
        }
        if after_ts:
            params['after'] = int(after_ts)

        # Paginate forward through new posts
        while max_results is None or len(results) < max_results:
            try:
                data = await self.make_request(f"{self.base_url}/search/submission", params=params)
                items = data.get('data', [])
                if not items:
                    break

                for item in items:
                    if item.get('selftext') in ('[removed]', '[deleted]'):
                        item['selftext'] = ''
                    if item.get('title'):
                        results.append(item)

                # Move forward
                newest_ts = max(item.get('created_utc', 0) for item in items)
                params['after'] = newest_ts

                if len(items) < 100:
                    break

            except Exception as e:
                logger.error(f"Pullpush incremental error: {e}")
                break

        return results

    async def _fetch_comments_batch(self, submissions: List[Dict]):
        """Fetch top comments for submissions"""
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
                        'body': c.get('body', '')[:2000],
                        'score': c.get('score', 0),
                    }
                    for c in comments
                    if c.get('body') not in ('[removed]', '[deleted]', '')
                ]
            except Exception as e:
                sub['top_comments'] = []

    async def fetch_details(self, external_id: str) -> Dict[str, Any]:
        return {}

    def extract_document_data(self, raw_data: Dict[str, Any]) -> Tuple[DocumentCreate, Optional[datetime]]:
        submission_id = raw_data.get('id', '')
        subreddit = raw_data.get('subreddit', 'unknown')
        author = raw_data.get('author', '[deleted]')
        title = raw_data.get('title', 'Untitled')
        selftext = raw_data.get('selftext', '')
        score = raw_data.get('score', 0)
        num_comments = raw_data.get('num_comments', 0)
        created_utc = raw_data.get('created_utc', 0)

        parts = [f"TITLE: {title}"]
        if selftext:
            parts.append(f"POST: {selftext[:5000]}")
        parts.append(f"Subreddit: r/{subreddit} | Score: {score} | Comments: {num_comments}")

        top_comments = raw_data.get('top_comments', [])
        if top_comments:
            parts.append("\nTOP COMMENTS:")
            for c in top_comments:
                parts.append(f"  [{c.get('score', 0)} pts] u/{c.get('author', '?')}: {c.get('body', '')}")

        content = "\n\n".join(parts)
        summary = f"{title[:200]} - r/{subreddit}"

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
