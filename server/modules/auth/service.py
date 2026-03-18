import jwt
import bcrypt
from datetime import datetime, timedelta
from typing import Optional, Dict
import os
from config.logger import logger
from config.database import db

# Secret key for JWT
SECRET_KEY = os.getenv("JWT_SECRET", "super-secret-key-change-this")
ALGORITHM = os.getenv("JWT_ALGORITHM", "HS256")
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", 1440))  # default 24h

class AuthService:
    
    @staticmethod
    def getPasswordHash(password: str) -> str:
        """Hash a password"""
        return bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')

    @staticmethod
    def verifyPassword(plainPassword: str, hashedPassword: str) -> bool:
        """Verify a password"""
        return bcrypt.checkpw(plainPassword.encode('utf-8'), hashedPassword.encode('utf-8'))

    @staticmethod
    def createAccessToken(data: dict, expiresDelta: Optional[timedelta] = None) -> str:
        """Create JWT token"""
        toEncode = data.copy()
        if expiresDelta:
            expire = datetime.utcnow() + expiresDelta
        else:
            expire = datetime.utcnow() + timedelta(minutes=15)
        toEncode.update({"exp": expire})
        encodedJwt = jwt.encode(toEncode, SECRET_KEY, algorithm=ALGORITHM)
        return encodedJwt

    async def registerUser(self, email: str, password: str, username: str = None, fullName: str = None) -> Dict:
        """Register a new user"""
        if not db.pool:
            raise Exception("Database not connected")
            
        async with db.pool.acquire() as conn:
            # Check if user exists
            existing = await conn.fetchrow("SELECT id FROM users WHERE email = $1", email)
            if existing:
                raise ValueError("Email already registered")
            
            hashedPw = self.getPasswordHash(password)
            
            # Insert user
            row = await conn.fetchrow(
                """INSERT INTO users (email, "passwordHash", username, "fullName") 
                   VALUES ($1, $2, $3, $4) 
                   RETURNING id, email, username, "fullName", role, "createdAt" """,
                email, hashedPw, username or email.split('@')[0], fullName
            )
            return dict(row)

    async def authenticateUser(self, email: str, password: str) -> Optional[Dict]:
        """Authenticate user by email"""
        if not db.pool:
            raise Exception("Database not connected")

        async with db.pool.acquire() as conn:
            user = await conn.fetchrow("SELECT * FROM users WHERE email = $1", email)
            if not user:
                return None
            
            if not self.verifyPassword(password, user['passwordHash']):
                return None
            
            userDict = dict(user)
            del userDict['passwordHash']
            return userDict
    
    async def getCurrentUserById(self, userId: str) -> Optional[Dict]:
        """Get user by ID"""
        if not db.pool:
             return None
        
        async with db.pool.acquire() as conn:
            user = await conn.fetchrow(
                """SELECT id, email, username, "fullName", role, preferences FROM users WHERE id = $1""",
                userId
            )
            return dict(user) if user else None

authService = AuthService()
