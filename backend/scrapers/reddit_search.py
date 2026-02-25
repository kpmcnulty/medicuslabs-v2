"""Reddit cross-subreddit search scraper.
Searches all of Reddit for disease terms, not just specific subreddits.
Uses PRAW's subreddit('all').search() to find relevant posts across all communities.
"""
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime
import praw
from loguru import logger

from .base import BaseScraper
from models.schemas import DocumentCreate
from core.config import settings


class RedditSearchScraper(BaseScraper):
    """Search ALL of Reddit for disease-related posts"""

    def __init__(self, source_id: int = None):
        super().__init__(
            source_id=source_id or 0,
            source_name="Reddit Search",
            rate_limit=60.0  # Reddit allows 60 req/min
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
        """Search all of Reddit for disease-related posts"""
        if not self.reddit:
            logger.error("Reddit API credentials not configured")
            return []

        max_results = kwargs.get('max_results') or 1000
        include_comments = kwargs.get('include_comments', True)
        comment_limit = kwargs.get('comment_limit', 10)

        logger.info(f"Searching all of Reddit for: {disease_term} (max {max_results})")

        results = []
        seen_ids = set()

        # Search with multiple sort strategies for broader coverage
        sort_options = ['relevance', 'new', 'top', 'comments']
        time_filters = ['month', 'year', 'all']

        for sort in sort_options:
            for time_filter in time_filters:
                if len(results) >= max_results:
                    break
                try:
                    remaining = max_results - len(results)
                    submissions = self.reddit.subreddit('all').search(
                        disease_term,
                        sort=sort,
                        time_filter=time_filter,
                        limit=min(remaining, 100)
                    )

                    for submission in submissions:
                        if submission.id in seen_ids:
                            continue
                        seen_ids.add(submission.id)

                        # Skip very low quality posts
                        if submission.score < 2 and submission.num_comments < 2:
                            continue

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

                        # Fetch top comments
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

                        if len(results) >= max_results:
                            break

                except Exception as e:
                    logger.warning(f"Error searching Reddit ({sort}/{time_filter}): {e}")

            if len(results) >= max_results:
                break

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
            content=content,
            summary=summary,
            metadata=metadata
        ), source_updated_at
