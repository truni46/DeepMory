from fastapi import APIRouter, Depends, Query
from typing import Dict
from common.deps import getCurrentUser
from modules.quota.service import quotaService
from config.logger import logger

router = APIRouter(prefix="/quota", tags=["Quota"])


@router.get("/status")
async def getQuotaStatus(
    conversationId: str = Query(default=""),
    user: Dict = Depends(getCurrentUser),
):
    try:
        status = await quotaService.getStatus(str(user["id"]), conversationId)
        return status
    except Exception as e:
        logger.error(f"getQuotaStatus failed: {e}")
        raise
