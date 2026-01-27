from fastapi import APIRouter, HTTPException, Depends
from fastapi.security import OAuth2PasswordRequestForm
from typing import Dict
from modules.auth.service import auth_service
from common.deps import get_current_user
from schemas import UserRegister, Token
from config.logger import logger

router = APIRouter(prefix="/auth", tags=["Auth"])

@router.post("/register", response_model=Token)
async def register(user_data: UserRegister):
    try:
        user = await auth_service.register_user(user_data.email, user_data.password, user_data.username, user_data.full_name)
        access_token = auth_service.create_access_token(data={"sub": str(user['id'])})
        return {"access_token": access_token, "token_type": "bearer", "user": user}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Register error: {e}")
        raise HTTPException(status_code=500, detail="Registration failed")

@router.post("/login", response_model=Token)
async def login(form_data: OAuth2PasswordRequestForm = Depends()):
    user = await auth_service.authenticate_user(form_data.username, form_data.password)
    if not user:
        raise HTTPException(status_code=401, detail="Incorrect email or password")
    
    access_token = auth_service.create_access_token(data={"sub": str(user['id'])})
    return {"access_token": access_token, "token_type": "bearer", "user": user}

@router.get("/me")
async def read_users_me(current_user: Dict = Depends(get_current_user)):
    return current_user
