"""
Short-term memory repository.
Hot path: Redis (context window + summary cache).
Cold path: PostgreSQL "conversationSummaries" table.
"""
from __future__ import annotations

import json
from typing import Dict, List, Optional
import os

from common.cacheService import cacheService
from config.database import db
from config.logger import logger

_WINDOW_TTL = int(os.getenv("REDIS_CONV_WINDOW_TTL", 3600))
_SUMMARY_TTL = int(os.getenv("REDIS_SUMMARY_TTL", 86400))
_WINDOW_SIZE = int(os.getenv("CONV_WINDOW_SIZE", 10))


class ConvMemoryRepository:

    @staticmethod
    def _windowKey(conversationId: str) -> str:
        return f"convWindow:{conversationId}"

    @staticmethod
    def _summaryKey(conversationId: str) -> str:
        return f"convSummary:{conversationId}"

    async def _getWindowFromDb(self, conversationId: str) -> List[Dict]:
        if not (db.useDatabase and db.pool):
            return []
        try:
            async with db.pool.acquire() as conn:
                rows = await conn.fetch(
                    """SELECT role, content FROM messages
                       WHERE "conversationId" = $1 AND role IN ('user', 'assistant')
                       ORDER BY "createdAt" DESC
                       LIMIT $2""",
                    conversationId, _WINDOW_SIZE,
                )
                if rows:
                    return [{"role": r["role"], "content": r["content"]} for r in reversed(rows)]
        except Exception as e:
            logger.warning(f"_getWindowFromDb failed for {conversationId}: {e}")
        return []

    async def getWindow(self, conversationId: str) -> List[Dict]:
        data = await cacheService.get(self._windowKey(conversationId))
        if isinstance(data, list) and data:
            return data
        return await self._getWindowFromDb(conversationId)

    async def setWindow(self, conversationId: str, window: List[Dict]) -> None:
        await cacheService.set(self._windowKey(conversationId), window, expire=_WINDOW_TTL)

    async def appendToWindow(self, conversationId: str, message: Dict) -> List[Dict]:
        window = await self.getWindow(conversationId)
        window.append(message)
        await self.setWindow(conversationId, window)
        return window

    async def clearWindow(self, conversationId: str) -> None:
        await cacheService.delete(self._windowKey(conversationId))

    async def getSummary(self, conversationId: str) -> Optional[str]:
        # Try Redis first
        cached = await cacheService.get(self._summaryKey(conversationId))
        if cached:
            return cached

        # Fall back to PostgreSQL
        if db.useDatabase and db.pool:
            async with db.pool.acquire() as conn:
                row = await conn.fetchrow(
                    """SELECT summary FROM "conversationSummaries" WHERE "conversationId" = $1""",
                    conversationId,
                )
                if row:
                    summary = row["summary"]
                    # Repopulate Redis cache
                    await cacheService.set(self._summaryKey(conversationId), summary, expire=_SUMMARY_TTL)
                    return summary
        return None

    async def upsertSummary(self, conversationId: str, summary: str, tokenCount: int = 0) -> None:
        # Write to Redis
        await cacheService.set(self._summaryKey(conversationId), summary, expire=_SUMMARY_TTL)

        # Persist to PostgreSQL
        if db.useDatabase and db.pool:
            async with db.pool.acquire() as conn:
                await conn.execute(
                    """INSERT INTO "conversationSummaries" ("conversationId", summary, "tokenCount", "updatedAt")
                       VALUES ($1, $2, $3, now())
                       ON CONFLICT ("conversationId")
                       DO UPDATE SET summary = EXCLUDED.summary,
                                     "tokenCount" = EXCLUDED."tokenCount",
                                     "updatedAt" = now()""",
                    conversationId, summary, tokenCount,
                )

    async def clearSummary(self, conversationId: str) -> None:
        await cacheService.delete(self._summaryKey(conversationId))
        if db.useDatabase and db.pool:
            async with db.pool.acquire() as conn:
                await conn.execute(
                    """DELETE FROM "conversationSummaries" WHERE "conversationId" = $1""",
                    conversationId,
                )


convMemoryRepository = ConvMemoryRepository()
