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
    """Reddit scraper using PRAW (Python Reddit API Wrapper)"""
    
    def __init__(self, source_id: int, source_name: str = "Reddit", rate_limit: float = 60.0):
        # Reddit allows 60 requests per minute
        super().__init__(source_id=source_id, source_name=source_name, rate_limit=rate_limit)
        
        # Get Reddit API credentials from settings
        self.client_id = settings.reddit_client_id or ''
        self.client_secret = settings.reddit_client_secret or ''
        self.user_agent = settings.reddit_user_agent
        
        # Initialize Reddit instance
        self.reddit = None
        if self.client_id and self.client_secret:
            self.reddit = praw.Reddit(
                client_id=self.client_id,
                client_secret=self.client_secret,
                user_agent=self.user_agent
            )
    
    async def search(self, disease_term: str, **kwargs) -> List[Dict[str, Any]]:
        """Search for posts in subreddit (for fixed sources, disease_term is ignored)"""
        if not self.reddit:
            logger.error("Reddit API credentials not configured")
            return []
        
        # Get configuration
        source_config = await self.get_source_config()
        job_config = await self.get_job_config()
        
        # For fixed sources, we need to get the subreddit from the source's config field
        # not the default_config field
        async with get_pg_connection() as conn:
            result = await conn.fetchrow(
                "SELECT config FROM sources WHERE id = $1",
                self.source_id
            )
            if result and result['config']:
                source_specific_config = result['config']
                if isinstance(source_specific_config, str):
                    source_specific_config = json.loads(source_specific_config)
            else:
                source_specific_config = {}
        
        # Check for subreddit in order: kwargs > job_config > source_specific_config > source_config
        subreddit_name = (kwargs.get('subreddit') or 
                         job_config.get('subreddit') or 
                         source_specific_config.get('subreddit') or
                         source_config.get('subreddit'))
        
        if not subreddit_name:
            logger.error(f"No subreddit configured for source {self.source_name}")
            return []
        
        # Get post settings
        post_limit = self.get_config_value(
            'post_limit', kwargs, job_config, source_config, 100
        )
        include_comments = self.get_config_value(
            'include_comments', kwargs, job_config, source_config, True
        )
        comment_limit = self.get_config_value(
            'comment_limit', kwargs, job_config, source_config, 10
        )
        sort_by = self.get_config_value(
            'sort_by', kwargs, job_config, source_config, 'hot'
        )
        
        # Check for incremental update
        since_date = kwargs.get('since_date')
        if since_date and isinstance(since_date, str):
            since_date = datetime.fromisoformat(since_date.replace('Z', '+00:00'))
        
        logger.info(f"Searching subreddit: r/{subreddit_name}")
        
        all_posts = []
        
        try:
            await self.rate_limiter.acquire()
            subreddit = self.reddit.subreddit(subreddit_name)
            
            # Get posts based on sort type
            if sort_by == 'hot':
                posts = subreddit.hot(limit=post_limit)
            elif sort_by == 'new':
                posts = subreddit.new(limit=post_limit)
            elif sort_by == 'top':
                posts = subreddit.top(limit=post_limit, time_filter='week')
            else:
                posts = subreddit.hot(limit=post_limit)
            
            # Process posts
            for post in posts:
                # Skip if post is too old for incremental update
                post_date = datetime.fromtimestamp(post.created_utc)
                if since_date and post_date < since_date:
                    continue
                
                # For fixed sources, we don't filter by disease relevance
                # All posts in the subreddit are considered relevant
                
                # Extract post data
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
                
                # Get top comments if enabled
                if include_comments and post.num_comments > 0:
                    await self.rate_limiter.acquire()
                    post.comments.replace_more(limit=0)  # Remove "load more" comments
                    top_comments = post.comments[:comment_limit]
                    
                    for comment in top_comments:
                        if hasattr(comment, 'body'):
                            post_data['comments'].append({
                                'id': comment.id,
                                'author': str(comment.author) if comment.author else '[deleted]',
                                'body': comment.body,
                                'score': comment.score,
                                'created_utc': comment.created_utc
                            })
                
                all_posts.append(post_data)
                
        except Exception as e:
            logger.error(f"Error fetching from r/{subreddit_name}: {e}")
        
        logger.info(f"Found {len(all_posts)} posts from r/{subreddit_name}")
        return all_posts
    
    def _is_relevant_post(self, post, disease_term: str) -> bool:
        """Check if a post is relevant to the disease term"""
        # Simple relevance check - can be enhanced with NLP
        disease_lower = disease_term.lower()
        text_to_check = f"{post.title} {post.selftext}".lower()
        
        # Check for disease term or common variations
        if disease_lower in text_to_check:
            return True
        
        # Check for common abbreviations or related terms
        # This could be expanded with a disease synonym mapping
        disease_keywords = {
            'multiple sclerosis': ['ms', 'multiple sclerosis', 'demyelinating'],
            'diabetes': ['diabetes', 'diabetic', 'blood sugar', 'insulin', 't1d', 't2d'],
            'lupus': ['lupus', 'sle', 'systemic lupus'],
            'parkinson': ['parkinson', 'parkinsons', "parkinson's", 'pd'],
            'alzheimer': ['alzheimer', 'alzheimers', "alzheimer's", 'dementia']
        }
        
        for key, terms in disease_keywords.items():
            if key in disease_lower:
                for term in terms:
                    if term in text_to_check:
                        return True
        
        return False
    
    async def fetch_details(self, post_id: str) -> Dict[str, Any]:
        """Fetch detailed information for a specific post"""
        if not self.reddit:
            logger.error("Reddit API credentials not configured")
            return {}
        
        try:
            await self.rate_limiter.acquire()
            submission = self.reddit.submission(id=post_id)
            submission.comments.replace_more(limit=0)
            
            # Get all comments
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
                'id': submission.id,
                'title': submission.title,
                'selftext': submission.selftext,
                'author': str(submission.author) if submission.author else '[deleted]',
                'url': f"https://reddit.com{submission.permalink}",
                'created_utc': submission.created_utc,
                'score': submission.score,
                'all_comments': all_comments
            }
            
        except Exception as e:
            logger.error(f"Error fetching post details for {post_id}: {e}")
            return {}
    
    def extract_document_data(self, raw_data: Dict[str, Any]) -> Tuple[DocumentCreate, Optional[datetime]]:
        """Extract and transform Reddit post data into DocumentCreate schema"""
        post_id = raw_data['id']
        
        # Build content from post and comments
        content_parts = []
        
        # Add post content
        content_parts.append(f"POST: {raw_data['title']}")
        if raw_data.get('selftext'):
            content_parts.append(f"CONTENT: {raw_data['selftext']}")
        
        # Add author info
        content_parts.append(f"AUTHOR: {raw_data['author']}")
        content_parts.append(f"COMMUNITY: r/{raw_data['subreddit']}")
        
        # Add engagement metrics
        content_parts.append(f"SCORE: {raw_data['score']} | REPLIES: {raw_data['num_comments']}")
        
        # Add top comments
        if raw_data.get('comments'):
            content_parts.append("\nTOP COMMENTS:")
            for i, comment in enumerate(raw_data['comments'][:5], 1):
                content_parts.append(f"\n{i}. {comment['author']} (score: {comment['score']}):")
                content_parts.append(f"   {comment['body'][:500]}...")
        
        content = "\n\n".join(content_parts)
        
        # Summary is title + first part of post
        summary = raw_data['title']
        if raw_data.get('selftext'):
            summary += f" - {raw_data['selftext'][:200]}"
        
        # Build metadata with generic field names
        metadata = {
            'post_id': post_id,
            'community': f"r/{raw_data['subreddit']}",  # Generic "community" instead of "subreddit"
            'author': raw_data['author'],
            'score': raw_data['score'],
            'reply_count': raw_data['num_comments'],  # Generic "reply_count" instead of "num_comments"
            'engagement_ratio': raw_data.get('upvote_ratio', 0),  # Generic engagement metric
            'created_date': datetime.fromtimestamp(raw_data['created_utc']).isoformat(),
            'category': raw_data.get('link_flair_text', ''),  # Generic "category" instead of "link_flair"
            'is_original_content': raw_data.get('is_self', True),  # Generic term
            'top_replies': [  # Generic "replies" instead of "comments"
                {
                    'author': c['author'],
                    'score': c['score'],
                    'created_date': datetime.fromtimestamp(c['created_utc']).isoformat()
                }
                for c in raw_data.get('comments', [])[:10]  # Store metadata for top 10 comments
            ]
        }
        
        # Extract post date
        source_updated_at = datetime.fromtimestamp(raw_data['created_utc'])
        
        return DocumentCreate(
            source_id=self.source_id,
            external_id=f"reddit_{post_id}",
            url=raw_data['url'],
            title=raw_data['title'],
            content=content,
            summary=summary[:500],  # Limit summary length
            metadata=metadata,
            scraped_at=datetime.now()
        ), source_updated_at