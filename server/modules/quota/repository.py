from datetime import datetime, timedelta
from typing import Optional
from config.logger import logger
from config.database import db
from common.cacheService import cacheService
from config.quota import quotaConfig


def getWeekStart() -> str:
    today = datetime.now()
    monday = today - timedelta(days=today.weekday())
    return monday.strftime("%Y-%m-%d")


class QuotaRepository:

    def _sessionKey(self, userId: str, conversationId: str) -> str:
        return f"quota:session:{userId}:{conversationId}"

    def _weeklyKey(self, userId: str) -> str:
        return f"quota:weekly:{userId}:{getWeekStart()}"

    async def getSessionUsage(self, userId: str, conversationId: str) -> Optional[int]:
        if not cacheService.redis:
            return None
        try:
            val = await cacheService.redis.get(self._sessionKey(userId, conversationId))
            return int(val) if val is not None else None
        except Exception as e:
            logger.error(f"getSessionUsage failed: {e}")
            return None

    async def getWeeklyUsage(self, userId: str) -> Optional[int]:
        if not cacheService.redis:
            return None
        try:
            val = await cacheService.redis.get(self._weeklyKey(userId))
            return int(val) if val is not None else None
        except Exception as e:
            logger.error(f"getWeeklyUsage failed: {e}")
            return None

    async def incrementUsage(self, userId: str, conversationId: str, tokens: int):
        if not cacheService.redis:
            logger.warning("Redis unavailable, skipping quota increment")
            return
        try:
            sessionKey = self._sessionKey(userId, conversationId)
            weeklyKey = self._weeklyKey(userId)

            pipe = cacheService.redis.pipeline()
            pipe.incrby(sessionKey, tokens)
            pipe.expire(sessionKey, quotaConfig.sessionDuration)
            pipe.incrby(weeklyKey, tokens)
            pipe.expire(weeklyKey, 7 * 24 * 3600)
            await pipe.execute()
        except Exception as e:
            logger.error(f"incrementUsage failed for user {userId}: {e}")

    async def rebuildSessionFromDb(self, userId: str, conversationId: str) -> int:
        total = 0
        try:
            if db.useDatabase and db.pool:
                cutoff = datetime.now() - timedelta(seconds=quotaConfig.sessionDuration)
                async with db.pool.acquire() as conn:
                    row = await conn.fetchrow(
                        """SELECT COALESCE(SUM((metadata->>'tokens')::int), 0) as total
                           FROM messages
                           WHERE "conversationId" = $1 AND "createdAt" >= $2""",
                        conversationId, cutoff
                    )
                    total = row["total"] if row else 0

            if cacheService.redis and total > 0:
                key = self._sessionKey(userId, conversationId)
                await cacheService.redis.set(key, total, ex=quotaConfig.sessionDuration)
                logger.info(f"Rebuilt session quota for user {userId}: {total} tokens")
        except Exception as e:
            logger.error(f"rebuildSessionFromDb failed for user {userId}: {e}")
        return total

    async def rebuildWeeklyFromDb(self, userId: str) -> int:
        total = 0
        try:
            if db.useDatabase and db.pool:
                weekStart = getWeekStart()
                async with db.pool.acquire() as conn:
                    row = await conn.fetchrow(
                        """SELECT COALESCE(SUM((metadata->>'tokens')::int), 0) as total
                           FROM messages m
                           JOIN conversations c ON m."conversationId" = c.id
                           WHERE c."userId" = $1 AND m."createdAt" >= $2::date""",
                        userId, weekStart
                    )
                    total = row["total"] if row else 0

            if cacheService.redis and total > 0:
                key = self._weeklyKey(userId)
                await cacheService.redis.set(key, total, ex=7 * 24 * 3600)
                logger.info(f"Rebuilt weekly quota for user {userId}: {total} tokens")
        except Exception as e:
            logger.error(f"rebuildWeeklyFromDb failed for user {userId}: {e}")
        return total

    async def getSessionTTL(self, userId: str, conversationId: str) -> int:
        if not cacheService.redis:
            return quotaConfig.sessionDuration
        try:
            ttl = await cacheService.redis.ttl(self._sessionKey(userId, conversationId))
            return max(ttl, 0)
        except Exception as e:
            logger.error(f"getSessionTTL failed: {e}")
            return 0


quotaRepository = QuotaRepository()
