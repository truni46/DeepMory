from datetime import datetime, timezone
from config.database import db
from common.cacheService import cacheService
from config.logger import logger


class SystemService:
    async def checkDb(self) -> str:
        try:
            if db.useDatabase and db.pool:
                async with db.pool.acquire() as conn:
                    await conn.fetchval("SELECT 1")
                return "ok"
            return "ok"
        except Exception as e:
            logger.warning(f"checkDb failed: {e}")
            return "down"

    async def checkRedis(self) -> str:
        try:
            if cacheService.redis is None:
                return "down"
            await cacheService.redis.ping()
            return "ok"
        except Exception as e:
            logger.warning(f"checkRedis failed: {e}")
            return "down"

    async def getHealth(self) -> dict:
        dbStatus = await self.checkDb()
        redisStatus = await self.checkRedis()
        overall = "ok" if dbStatus == "ok" and redisStatus == "ok" else "degraded"
        return {
            "status": overall,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "db": dbStatus,
            "redis": redisStatus,
        }


systemService = SystemService()
