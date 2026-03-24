"""
Short-term memory repository.
Hot path: Redis (context window + summary cache).
Cold path: PostgreSQL conversation_summaries table.
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


class ConvMemoryRepository:

    # ---- Redis keys ----------------------------------------------------------

    @staticmethod
    def _windowKey(conversationId: str) -> str:
        return f"conv_window:{conversationId}"

    @staticmethod
    def _summaryKey(conversationId: str) -> str:
        return f"conv_summary:{conversationId}"

    # ---- Window (Redis) -------------------------------------------------------

    async def getWindow(self, conversationId: str) -> List[Dict]:
        data = await cacheService.get(self._windowKey(conversationId))
        return data if isinstance(data, list) else []

    async def setWindow(self, conversationId: str, window: List[Dict]) -> None:
        await cacheService.set(self._windowKey(conversationId), window, expire=_WINDOW_TTL)

    async def appendToWindow(self, conversationId: str, message: Dict) -> List[Dict]:
        window = await self.getWindow(conversationId)
        window.append(message)
        await self.setWindow(conversationId, window)
        return window

    async def clearWindow(self, conversationId: str) -> None:
        await cacheService.delete(self._windowKey(conversationId))

    # ---- Summary (Redis hot + PostgreSQL cold) --------------------------------

    async def getSummary(self, conversationId: str) -> Optional[str]:
        # Try Redis first
        cached = await cacheService.get(self._summaryKey(conversationId))
        if cached:
            return cached

        # Fall back to PostgreSQL
        if db.useDatabase and db.pool:
            async with db.pool.acquire() as conn:
                row = await conn.fetchrow(
                    """SELECT summary FROM conversation_summaries WHERE "conversationId" = $1""",
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
                    """INSERT INTO conversation_summaries ("conversationId", summary, "tokenCount", "updatedAt")
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
                    """DELETE FROM conversation_summaries WHERE "conversationId" = $1""",
                    conversationId,
                )


convMemoryRepository = ConvMemoryRepository()
