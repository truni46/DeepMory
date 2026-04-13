from typing import Dict
from config.quota import quotaConfig
from config.logger import logger
from modules.quota.repository import quotaRepository, getWeekStart


class QuotaService:

    async def checkQuota(self, userId: str, conversationId: str) -> Dict:
        sessionUsed = await quotaRepository.getSessionUsage(userId, conversationId)
        if sessionUsed is None:
            sessionUsed = await quotaRepository.rebuildSessionFromDb(userId, conversationId)

        weeklyUsed = await quotaRepository.getWeeklyUsage(userId)
        if weeklyUsed is None:
            weeklyUsed = await quotaRepository.rebuildWeeklyFromDb(userId)

        sessionPercent = sessionUsed / quotaConfig.sessionLimit if quotaConfig.sessionLimit > 0 else 0
        weeklyPercent = weeklyUsed / quotaConfig.weeklyLimit if quotaConfig.weeklyLimit > 0 else 0

        maxPercent = max(sessionPercent, weeklyPercent)
        allowed = maxPercent < 1.0
        warning = maxPercent >= quotaConfig.warningThreshold and maxPercent < 1.0

        sessionTTL = await quotaRepository.getSessionTTL(userId, conversationId)

        return {
            "allowed": allowed,
            "warning": warning,
            "session": {
                "used": sessionUsed,
                "limit": quotaConfig.sessionLimit,
                "percent": round(sessionPercent, 4),
                "remainingSeconds": sessionTTL,
            },
            "weekly": {
                "used": weeklyUsed,
                "limit": quotaConfig.weeklyLimit,
                "percent": round(weeklyPercent, 4),
                "resetDay": getWeekStart(),
            },
        }

    async def incrementUsage(self, userId: str, conversationId: str, tokens: int):
        if tokens <= 0:
            return
        await quotaRepository.incrementUsage(userId, conversationId, tokens)
        logger.info(f"Quota incremented for user {userId}: +{tokens} tokens")

    async def getStatus(self, userId: str, conversationId: str) -> Dict:
        return await self.checkQuota(userId, conversationId)


quotaService = QuotaService()
