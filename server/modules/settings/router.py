from fastapi import APIRouter, Depends, HTTPException
from typing import Dict
from common.deps import get_current_user
from modules.settings.service import settingsService

router = APIRouter(prefix="/settings", tags=["Settings"])

@router.get("", response_model=Dict)
async def getSettings(user: Dict = Depends(get_current_user)):
    """Get current user settings"""
    return await settingsService.get_user_settings(str(user['id']))

@router.put("", response_model=Dict)
async def updateSettings(updates: Dict, user: Dict = Depends(get_current_user)):
    """Update user settings"""
    try:
        return await settingsService.update_user_settings(str(user['id']), updates)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
