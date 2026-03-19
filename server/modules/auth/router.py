from fastapi import APIRouter, HTTPException, Depends
from datetime import timedelta
from typing import Dict
from modules.auth.service import authService, ACCESS_TOKEN_EXPIRE_MINUTES
from common.deps import get_current_user
from schemas import UserRegister, UserLogin, Token
from config.logger import logger

router = APIRouter(prefix="/auth", tags=["Auth"])

@router.post("/register", response_model=Token)
async def register(userData: UserRegister):
    try:
        user = await authService.registerUser(userData.email, userData.password, userData.username, userData.fullName)
        accessToken = authService.createAccessToken(
            data={"sub": str(user['id'])},
            expiresDelta=timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
        )
        return {"access_token": accessToken, "token_type": "bearer", "user": user}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Register error: {e}")
        raise HTTPException(status_code=500, detail="Registration failed")

from fastapi.security import OAuth2PasswordRequestForm

@router.post("/login", response_model=Token)
async def login(formData: OAuth2PasswordRequestForm = Depends()):
    """Login with username (email) + password (Form Data)"""
    user = await authService.authenticateUser(formData.username, formData.password)
    if not user:
        raise HTTPException(status_code=401, detail="Incorrect email or password")
    
    accessToken = authService.createAccessToken(
        data={"sub": str(user['id'])},
        expiresDelta=timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    )
    return {"access_token": accessToken, "token_type": "bearer", "user": user}

@router.get("/me")
async def readUsersMe(currentUser: Dict = Depends(get_current_user)):
    return currentUser
