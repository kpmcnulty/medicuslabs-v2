import asyncio
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime, timedelta
import praw
from loguru import logger
import json

from .base import BaseScraper
from models.schemas import DocumentCreate
from core.config import settings
from core.database import get_pg_connection

class RedditScraper(BaseScraper):
    """Reddit scraper using PRAW with cursor-based resume.
    
    Note: Reddit's API hard-caps listings at ~1000 results per listing type.
    We save what we get and mark exhausted. Incremental runs get new posts.
    """
    
    def __init__(self, source_id: int, source_name: str = "Reddit", rate_limit: float = 60.0):
        super().__init__(source_id=source_id, source_name=source_name, rate_limit=rate_limit)
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
        """Search subreddit with cursor-based resume"""
        if not self.reddit:
            logger.error("Reddit API credentials not configured")
            return []
        
        source_config = await self.get_source_config()
        job_config = await self.get_job_config()
        
        async with get_pg_connection() as conn:
            result = await conn.fetchrow(
                "SELECT config FROM sources WHERE id = $1", self.source_id
            )
            source_specific_config = {}
            if result and result['config']:
                source_specific_config = result['config']
                if isinstance(source_specific_config, str):
                    source_specific_config = json.loads(source_specific_config)
        
        subreddit_name = (kwargs.get('subreddit') or job_config.get('subreddit') or 
                         source_specific_config.get('subreddit') or source_config.get('subreddit'))
        
        if not subreddit_name:
            logger.error(f"No subreddit configured for source {self.source_name}")
            return []
        
        # Reddit PRAW hard-caps at ~1000 per listing — no way around this
        post_limit = kwargs.get('max_results')  # None = get all (up to Reddit's ~1000 cap)
        if post_limit is None:
            post_limit = 1000  # Reddit API hard limit
        
        include_comments = self.get_config_value('include_comments', kwargs, job_config, source_config, True)
        comment_limit = self.get_config_value('comment_limit', kwargs, job_config, source_config, 10)
        sort_by = self.get_config_value('sort_by', kwargs, job_config, source_config, 'hot')
        
        # Load cursor
        cursor = await self.get_cursor(disease_term)
        newest_seen_utc = cursor.get('newest_seen_utc')
        exhausted = cursor.get('exhausted', False)
        
        since_date = kwargs.get('since_date')
        if since_date and isinstance(since_date, str):
            since_date = datetime.fromisoformat(since_date.replace('Z', '+00:00'))
        
        if exhausted and newest_seen_utc:
            # Incremental: only get posts newer than what we've seen
            if not since_date:
                since_date = datetime.fromtimestamp(newest_seen_utc)
            logger.info(f"Reddit: Incremental for r/{subreddit_name} since {since_date}")
        
        logger.info(f"Searching subreddit: r/{subreddit_name}")
        
        all_posts = []
        
        try:
            await self.rate_limiter.acquire()
            subreddit = self.reddit.subreddit(subreddit_name)
            
            if sort_by == 'hot':
                posts = subreddit.hot(limit=post_limit)
            elif sort_by == 'new':
                posts = subreddit.new(limit=post_limit)
            elif sort_by == 'top':
                posts = subreddit.top(limit=post_limit, time_filter='week')
            else:
                posts = subreddit.hot(limit=post_limit)
            
            for post in posts:
                post_date = datetime.fromtimestamp(post.created_utc)
                if since_date and post_date < since_date:
                    continue
                
                post_data = {
                    'id': post.id,
                    'subreddit': subreddit_name,
                    'title': post.title,
                    'author': str(post.author) if post.author else '[deleted]',
                    'selftext': post.selftext,
                    'url': f"https://reddit.com{post.permalink}",
                    'created_utc': post.created_utc,
                    'score': post.score,
                    'num_comments': post.num_comments,
                    'upvote_ratio': post.upvote_ratio,
                    'link_flair_text': post.link_flair_text,
                    'is_self': post.is_self,
                    'comments': []
                }
                
                # Track newest
                if not newest_seen_utc or post.created_utc > newest_seen_utc:
                    newest_seen_utc = post.created_utc
                
                if include_comments and post.num_comments > 0:
                    await self.rate_limiter.acquire()
                    post.comments.replace_more(limit=0)
                    for comment in post.comments[:comment_limit]:
                        if hasattr(comment, 'body'):
                            post_data['comments'].append({
                                'id': comment.id,
                                'author': str(comment.author) if comment.author else '[deleted]',
                                'body': comment.body,
                                'score': comment.score,
                                'created_utc': comment.created_utc
                            })
                
                all_posts.append(post_data)
                
                # Save cursor every 100 posts
                if len(all_posts) % 100 == 0:
                    await self.save_cursor(disease_term, newest_seen_utc=newest_seen_utc)
                
        except Exception as e:
            logger.error(f"Error fetching from r/{subreddit_name}: {e}")
            await self.save_cursor(disease_term, newest_seen_utc=newest_seen_utc)
        
        # Save final cursor and mark exhausted (Reddit caps at ~1000)
        await self.save_cursor(disease_term, newest_seen_utc=newest_seen_utc)
        await self.mark_exhausted(disease_term)
        
        logger.info(f"Found {len(all_posts)} posts from r/{subreddit_name}")
        return all_posts
    
    async def fetch_details(self, post_id: str) -> Dict[str, Any]:
        if not self.reddit:
            return {}
        try:
            await self.rate_limiter.acquire()
            submission = self.reddit.submission(id=post_id)
            submission.comments.replace_more(limit=0)
            all_comments = []
            for comment in submission.comments.list():
                if hasattr(comment, 'body'):
                    all_comments.append({
                        'id': comment.id,
                        'author': str(comment.author) if comment.author else '[deleted]',
                        'body': comment.body,
                        'score': comment.score,
                        'created_utc': comment.created_utc
                    })
            return {
                'id': submission.id, 'title': submission.title,
                'selftext': submission.selftext,
                'author': str(submission.author) if submission.author else '[deleted]',
                'url': f"https://reddit.com{submission.permalink}",
                'created_utc': submission.created_utc,
                'score': submission.score, 'all_comments': all_comments
            }
        except Exception as e:
            logger.error(f"Error fetching post details for {post_id}: {e}")
            return {}
    
    def extract_document_data(self, raw_data: Dict[str, Any]) -> Tuple[DocumentCreate, Optional[datetime]]:
        post_id = raw_data['id']
        
        content_parts = [f"POST: {raw_data['title']}"]
        if raw_data.get('selftext'):
            content_parts.append(f"CONTENT: {raw_data['selftext']}")
        content_parts.append(f"AUTHOR: {raw_data['author']}")
        content_parts.append(f"COMMUNITY: r/{raw_data['subreddit']}")
        content_parts.append(f"SCORE: {raw_data['score']} | REPLIES: {raw_data['num_comments']}")
        
        if raw_data.get('comments'):
            content_parts.append("\nTOP COMMENTS:")
            for i, comment in enumerate(raw_data['comments'][:5], 1):
                content_parts.append(f"\n{i}. {comment['author']} (score: {comment['score']}):")
                content_parts.append(f"   {comment['body'][:500]}...")
        
        content = "\n\n".join(content_parts)
        summary = raw_data['title']
        if raw_data.get('selftext'):
            summary += f" - {raw_data['selftext'][:200]}"
        
        post_created = datetime.fromtimestamp(raw_data['created_utc'])
        last_activity = post_created
        if raw_data.get('comments'):
            for comment in raw_data['comments']:
                comment_date = datetime.fromtimestamp(comment['created_utc'])
                if comment_date > last_activity:
                    last_activity = comment_date
        
        metadata = {
            'post_id': post_id,
            'community': f"r/{raw_data['subreddit']}",
            'author': raw_data['author'],
            'score': raw_data['score'],
            'reply_count': raw_data['num_comments'],
            'engagement_ratio': raw_data.get('upvote_ratio', 0),
            'posted_date': post_created.isoformat(),
            'last_activity_date': last_activity.isoformat(),
            'category': raw_data.get('link_flair_text', ''),
            'is_original_content': raw_data.get('is_self', True),
            'top_replies': [
                {
                    'author': c['author'], 'body': c['body'],
                    'score': c['score'],
                    'posted_date': datetime.fromtimestamp(c['created_utc']).isoformat()
                }
                for c in raw_data.get('comments', [])[:10]
            ]
        }
        
        return DocumentCreate(
            source_id=self.source_id,
            external_id=f"reddit_{post_id}",
            url=raw_data['url'], title=raw_data['title'],
            content=content, summary=summary[:500],
            metadata=metadata
        ), last_activity
