"""Reddit cross-subreddit search scraper with cursor-based resume.
Searches all of Reddit for disease terms.

Note: Reddit's API hard-caps at ~1000 results per search query.
We use multiple sort/time combinations to maximize coverage, but
total unique results are still limited by Reddit.
"""
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime
import praw
from loguru import logger

from .base import BaseScraper
from models.schemas import DocumentCreate
from core.config import settings


class RedditSearchScraper(BaseScraper):
    """Search ALL of Reddit with cursor-based resume"""

    def __init__(self, source_id: int = None):
        super().__init__(
            source_id=source_id or 0,
            source_name="Reddit Search",
            rate_limit=60.0
        )
        self.client_id = settings.reddit_client_id or ''
        self.client_secret = settings.reddit_client_secret or ''
        self.user_agent = settings.reddit_user_agent
        self.reddit = None
        if self.client_id and self.client_secret:
            self.reddit = praw.Reddit(
                client_id=self.client_id,
                client_secret=self.client_secret,
                user_agent=self.user_agent
            )

    async def search(self, disease_term: str, **kwargs) -> List[Dict[str, Any]]:
        """Search all of Reddit with cursor-based resume.
        
        Reddit API hard-caps at ~1000 per listing. We try multiple sort/time
        combos and save cursor for incremental.
        """
        if not self.reddit:
            logger.error("Reddit API credentials not configured")
            return []

        max_results = kwargs.get('max_results')  # None = unlimited (up to Reddit's ~1000 cap per combo)
        include_comments = kwargs.get('include_comments', True)
        comment_limit = kwargs.get('comment_limit', 10)

        # Load cursor
        cursor = await self.get_cursor(disease_term)
        newest_seen_utc = cursor.get('newest_seen_utc')
        exhausted = cursor.get('exhausted', False)
        completed_combos = cursor.get('completed_combos', [])

        if exhausted:
            logger.info(f"Reddit Search: Exhausted for '{disease_term}', incremental mode")
            completed_combos = []  # Reset combos for fresh incremental run

        logger.info(f"Searching all of Reddit for: {disease_term}")

        results = []
        seen_ids = set()

        sort_options = ['relevance', 'new', 'top', 'comments']
        time_filters = ['month', 'year', 'all']

        for sort in sort_options:
            for time_filter in time_filters:
                combo_key = f"{sort}_{time_filter}"
                if combo_key in completed_combos:
                    continue

                if max_results is not None and len(results) >= max_results:
                    break

                try:
                    remaining = (max_results - len(results)) if max_results else 1000
                    submissions = self.reddit.subreddit('all').search(
                        disease_term, sort=sort, time_filter=time_filter,
                        limit=min(remaining, 100)
                    )

                    for submission in submissions:
                        if submission.id in seen_ids:
                            continue
                        seen_ids.add(submission.id)

                        if submission.score < 2 and submission.num_comments < 2:
                            continue

                        # Track newest
                        if not newest_seen_utc or submission.created_utc > newest_seen_utc:
                            newest_seen_utc = submission.created_utc

                        post_data = {
                            'post_id': submission.id,
                            'title': submission.title,
                            'content': submission.selftext or '',
                            'author': str(submission.author) if submission.author else '[deleted]',
                            'subreddit': str(submission.subreddit),
                            'score': submission.score,
                            'num_comments': submission.num_comments,
                            'created_utc': submission.created_utc,
                            'url': f"https://reddit.com{submission.permalink}",
                            'link_url': submission.url if not submission.is_self else None,
                            'upvote_ratio': submission.upvote_ratio,
                            'is_self': submission.is_self,
                            'top_replies': []
                        }

                        if include_comments and submission.num_comments > 0:
                            try:
                                submission.comment_sort = 'best'
                                submission.comments.replace_more(limit=0)
                                for comment in submission.comments[:comment_limit]:
                                    if hasattr(comment, 'body') and comment.body and comment.body != '[deleted]':
                                        post_data['top_replies'].append({
                                            'body': comment.body[:2000],
                                            'author': str(comment.author) if comment.author else '[deleted]',
                                            'score': comment.score,
                                            'posted_date': datetime.utcfromtimestamp(comment.created_utc).isoformat()
                                        })
                            except Exception as e:
                                logger.debug(f"Error fetching comments for {submission.id}: {e}")

                        results.append(post_data)
                        if max_results is not None and len(results) >= max_results:
                            break

                    # Mark this combo as done
                    completed_combos.append(combo_key)
                    await self.save_cursor(disease_term, newest_seen_utc=newest_seen_utc,
                                          completed_combos=completed_combos)

                except Exception as e:
                    logger.warning(f"Error searching Reddit ({sort}/{time_filter}): {e}")
                    await self.save_cursor(disease_term, newest_seen_utc=newest_seen_utc,
                                          completed_combos=completed_combos)

            if max_results is not None and len(results) >= max_results:
                break

        # Mark exhausted after all combos
        await self.save_cursor(disease_term, newest_seen_utc=newest_seen_utc,
                              completed_combos=completed_combos)
        if len(completed_combos) >= len(sort_options) * len(time_filters):
            await self.mark_exhausted(disease_term)

        logger.info(f"Found {len(results)} posts across Reddit for '{disease_term}' "
                    f"from {len(set(r['subreddit'] for r in results))} subreddits")
        return results

    async def fetch_details(self, post_id: str) -> Dict[str, Any]:
        return {}

    def extract_document_data(self, raw_data: Dict[str, Any]) -> Tuple[DocumentCreate, Optional[datetime]]:
        post_id = raw_data['post_id']

        content_parts = []
        if raw_data.get('title'):
            content_parts.append(f"TITLE: {raw_data['title']}")
        if raw_data.get('content'):
            content_parts.append(f"CONTENT: {raw_data['content']}")
        if raw_data.get('subreddit'):
            content_parts.append(f"SUBREDDIT: r/{raw_data['subreddit']}")
        content_parts.append(f"SCORE: {raw_data.get('score', 0)} | COMMENTS: {raw_data.get('num_comments', 0)}")

        if raw_data.get('top_replies'):
            content_parts.append("\nTOP REPLIES:")
            for i, reply in enumerate(raw_data['top_replies'][:10], 1):
                content_parts.append(f"\n{i}. u/{reply.get('author', 'unknown')} (score: {reply.get('score', 0)}):")
                content_parts.append(f"   {reply['body'][:1000]}")

        content = "\n\n".join(content_parts)
        summary = raw_data.get('title', '')
        if raw_data.get('content'):
            summary += f" - {raw_data['content'][:200]}"
        summary = summary[:500]

        source_updated_at = None
        posted_date = None
        if raw_data.get('created_utc'):
            source_updated_at = datetime.utcfromtimestamp(raw_data['created_utc'])
            posted_date = source_updated_at.isoformat()

        metadata = {
            'post_id': post_id,
            'community': f"r/{raw_data.get('subreddit', '')}",
            'author': raw_data.get('author', '[deleted]'),
            'score': raw_data.get('score', 0),
            'reply_count': raw_data.get('num_comments', 0),
            'posted_date': posted_date,
            'upvote_ratio': raw_data.get('upvote_ratio', 0),
            'is_self': raw_data.get('is_self', True),
        }

        return DocumentCreate(
            source_id=self.source_id,
            external_id=f"reddit_search_{post_id}",
            url=raw_data.get('url', ''),
            title=raw_data.get('title', 'Untitled'),
            content=content, summary=summary, metadata=metadata
        ), source_updated_at
