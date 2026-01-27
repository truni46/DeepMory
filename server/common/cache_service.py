import json
from typing import Any, Optional
import redis.asyncio as redis
from config.redis import redis_config
from config.logger import logger

class CacheService:
    def __init__(self):
        self.redis: Optional[redis.Redis] = None
        
    async def connect(self):
        """Connect to Redis"""
        try:
            self.redis = redis.from_url(
                redis_config.redis_url, 
                encoding="utf-8", 
                decode_responses=True
            )
            await self.redis.ping()
            logger.info(f"Connected to Redis at {redis_config.host}:{redis_config.port}")
        except Exception as e:
            logger.error(f"Failed to connect to Redis: {e}")
            self.redis = None

    async def close(self):
        """Close Redis connection"""
        if self.redis:
            await self.redis.close()
            logger.info("Redis connection closed")

    async def get(self, key: str) -> Any:
        """Get value from cache"""
        if not self.redis:
            return None
        try:
            val = await self.redis.get(key)
            if val:
                return json.loads(val)
        except Exception as e:
            logger.error(f"Error reading from cache: {e}")
        return None

    async def set(self, key: str, value: Any, expire: int = 3600):
        """Set value in cache with expiration (default 1 hour)"""
        if not self.redis:
            return
        try:
            await self.redis.set(key, json.dumps(value), ex=expire)
        except Exception as e:
            logger.error(f"Error writing to cache: {e}")

    async def delete(self, key: str):
        """Delete value from cache"""
        if not self.redis:
            return
        try:
            await self.redis.delete(key)
        except Exception as e:
            logger.error(f"Error deleting from cache: {e}")

    async def exists(self, key: str) -> bool:
        """Check if key exists"""
        if not self.redis:
            return False
        try:
            return await self.redis.exists(key) > 0
        except Exception as e:
            logger.error(f"Error checking cache existence: {e}")
            return False

# Global instance
cache_service = CacheService()
