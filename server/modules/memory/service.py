from typing import List, Dict
from config.database import db
from config.logger import logger

class MemoryService:
    
    async def add_memory(self, userId: str, content: str, context: Dict = None):
        """Add a memory item"""
        if not db.pool:
            return
            
        async with db.pool.acquire() as conn:
            await conn.execute(
                """INSERT INTO memories ("userId", content, context) 
                   VALUES ($1, $2, $3)""",
                userId, content, context or {}
            )

    async def retrieve_memories(self, userId: str, query: str = None, limit: int = 5) -> List[Dict]:
        """Retrieve relevant memories"""
        if not db.pool:
            return []
            
        async with db.pool.acquire() as conn:
            rows = await conn.fetch(
                """SELECT * FROM memories WHERE "userId" = $1 ORDER BY "createdAt" DESC LIMIT $2""",
                userId, limit
            )
            return [dict(row) for row in rows]

memoryService = MemoryService()
