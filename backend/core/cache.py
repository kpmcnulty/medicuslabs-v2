"""Redis cache client for query result caching"""
import json
import hashlib
from typing import Optional, Any, Dict, List
from datetime import timedelta
import redis.asyncio as redis
from .config import settings
import logging

logger = logging.getLogger(__name__)

class CacheClient:
    """Redis cache client with automatic serialization"""
    
    def __init__(self):
        self.redis_client = None
        self.default_ttl = 3600  # 1 hour default
        
    async def connect(self):
        """Initialize Redis connection"""
        if not self.redis_client:
            self.redis_client = redis.from_url(
                settings.redis_url,
                decode_responses=True,
                db=1  # Use db1 for query cache
            )
            await self.redis_client.ping()
            logger.info("Redis cache connected")
    
    async def disconnect(self):
        """Close Redis connection"""
        if self.redis_client:
            await self.redis_client.close()
            
    def _generate_key(self, prefix: str, params: Dict[str, Any]) -> str:
        """Generate cache key from prefix and parameters"""
        # Sort params for consistent keys
        sorted_params = json.dumps(params, sort_keys=True)
        hash_digest = hashlib.md5(sorted_params.encode()).hexdigest()
        return f"{prefix}:{hash_digest}"
    
    async def get(self, key: str) -> Optional[Any]:
        """Get value from cache"""
        try:
            if not self.redis_client:
                await self.connect()
                
            value = await self.redis_client.get(key)
            if value:
                return json.loads(value)
            return None
        except Exception as e:
            logger.error(f"Cache get error: {e}")
            return None
    
    async def set(self, key: str, value: Any, ttl: Optional[int] = None) -> bool:
        """Set value in cache with TTL"""
        try:
            if not self.redis_client:
                await self.connect()
                
            ttl = ttl or self.default_ttl
            serialized = json.dumps(value, default=str)
            await self.redis_client.setex(key, ttl, serialized)
            return True
        except Exception as e:
            logger.error(f"Cache set error: {e}")
            return False
    
    async def delete(self, key: str) -> bool:
        """Delete key from cache"""
        try:
            if not self.redis_client:
                await self.connect()
                
            await self.redis_client.delete(key)
            return True
        except Exception as e:
            logger.error(f"Cache delete error: {e}")
            return False
    
    async def delete_pattern(self, pattern: str) -> int:
        """Delete all keys matching pattern"""
        try:
            if not self.redis_client:
                await self.connect()
                
            keys = await self.redis_client.keys(pattern)
            if keys:
                return await self.redis_client.delete(*keys)
            return 0
        except Exception as e:
            logger.error(f"Cache delete pattern error: {e}")
            return 0
    
    # Query-specific cache methods
    async def get_search_results(
        self, 
        query: str, 
        filters: Dict[str, Any], 
        page: int, 
        limit: int
    ) -> Optional[Dict[str, Any]]:
        """Get cached search results"""
        params = {
            "query": query,
            "filters": filters,
            "page": page,
            "limit": limit
        }
        key = self._generate_key("search", params)
        return await self.get(key)
    
    async def set_search_results(
        self, 
        query: str, 
        filters: Dict[str, Any], 
        page: int, 
        limit: int,
        results: Dict[str, Any],
        ttl: int = 1800  # 30 minutes for search results
    ) -> bool:
        """Cache search results"""
        params = {
            "query": query,
            "filters": filters,
            "page": page,
            "limit": limit
        }
        key = self._generate_key("search", params)
        return await self.set(key, results, ttl)
    
    async def get_facets(
        self, 
        filters: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        """Get cached facet counts"""
        key = self._generate_key("facets", filters)
        return await self.get(key)
    
    async def set_facets(
        self, 
        filters: Dict[str, Any],
        facets: Dict[str, Any],
        ttl: int = 600  # 10 minutes for facets
    ) -> bool:
        """Cache facet counts"""
        key = self._generate_key("facets", filters)
        return await self.set(key, facets, ttl)
    
    async def invalidate_search_cache(self):
        """Invalidate all search cache entries"""
        deleted = await self.delete_pattern("search:*")
        deleted += await self.delete_pattern("facets:*")
        logger.info(f"Invalidated {deleted} cache entries")
        return deleted

# Global cache instance
cache_client = CacheClient()

# Dependency for FastAPI
async def get_cache() -> CacheClient:
    return cache_client