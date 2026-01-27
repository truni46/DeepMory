import jwt
import bcrypt
from datetime import datetime, timedelta
from typing import Optional, Dict
import os
from config.logger import logger
from config.database import db

# Secret key for JWT
SECRET_KEY = os.getenv("JWT_SECRET", "super-secret-key-change-this")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24  # 1 day

class AuthService:
    
    @staticmethod
    def get_password_hash(password: str) -> str:
        """Hash a password"""
        return bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')

    @staticmethod
    def verify_password(plain_password: str, hashed_password: str) -> bool:
        """Verify a password"""
        return bcrypt.checkpw(plain_password.encode('utf-8'), hashed_password.encode('utf-8'))

    @staticmethod
    def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
        """Create JWT token"""
        to_encode = data.copy()
        if expires_delta:
            expire = datetime.utcnow() + expires_delta
        else:
            expire = datetime.utcnow() + timedelta(minutes=15)
        to_encode.update({"exp": expire})
        encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
        return encoded_jwt

    async def register_user(self, email: str, password: str, username: str = None, full_name: str = None) -> Dict:
        """Register a new user"""
        if not db.pool:
            raise Exception("Database not connected")
            
        async with db.pool.acquire() as conn:
            # Check if user exists
            existing = await conn.fetchrow("SELECT id FROM users WHERE email = $1", email)
            if existing:
                raise ValueError("Email already registered")
            
            hashed_pw = self.get_password_hash(password)
            
            # Insert user
            row = await conn.fetchrow(
                """INSERT INTO users (email, password_hash, username, full_name) 
                   VALUES ($1, $2, $3, $4) 
                   RETURNING id, email, username, full_name, role, created_at""",
                email, hashed_pw, username or email.split('@')[0], full_name
            )
            return dict(row)

    async def authenticate_user(self, email: str, password: str) -> Optional[Dict]:
        """Authenticate user"""
        if not db.pool:
            raise Exception("Database not connected")

        async with db.pool.acquire() as conn:
            user = await conn.fetchrow("SELECT * FROM users WHERE email = $1", email)
            if not user:
                return None
            
            if not self.verify_password(password, user['password_hash']):
                return None
            
            # Return user dict without password
            user_dict = dict(user)
            del user_dict['password_hash']
            return user_dict
    
    async def get_current_user_by_id(self, user_id: str) -> Optional[Dict]:
        """Get user by ID"""
        if not db.pool:
             return None
        
        async with db.pool.acquire() as conn:
            user = await conn.fetchrow("SELECT id, email, username, full_name, role, preferences FROM users WHERE id = $1", user_id)
            return dict(user) if user else None

auth_service = AuthService()
