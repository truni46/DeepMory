from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from typing import Dict, Annotated
import jwt
import os
from modules.auth.service import authService

# Load secret directly from environment to avoid import order issues
SECRET_KEY = os.getenv("JWT_SECRET", "super-secret-key-change-this")
ALGORITHM = os.getenv("JWT_ALGORITHM", "HS256")

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="api/auth/login")

async def get_current_user(token: Annotated[str, Depends(oauth2_scheme)]) -> Dict:
    credentialsException = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        print(f"DEBUG AUTH: token recibed={token[:10]}... key={SECRET_KEY[:5]}...")
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        userId: str = payload.get("sub")
        print(f"DEBUG AUTH: decoded sub={userId}")
        if userId is None:
            print("DEBUG AUTH: sub is None")
            raise credentialsException
    except jwt.PyJWTError as e:
        import logging
        logging.error(f"JWT decode error: {e}")
        print(f"DEBUG AUTH: JWT Error = {e}")
        raise credentialsException
        
    user = await authService.getCurrentUserById(userId)
    if user is None:
        print(f"DEBUG AUTH: User {userId} not found in DB")
        raise credentialsException
    return user
