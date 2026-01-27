from typing import List, Dict
from config.database import db
from config.logger import logger

class MemoryService:
    
    async def add_memory(self, user_id: str, content: str, context: Dict = None):
        """Add a memory item"""
        if not db.pool:
            return
            
        async with db.pool.acquire() as conn:
            await conn.execute(
                """INSERT INTO memories (user_id, content, context) 
                   VALUES ($1, $2, $3)""",
                user_id, content, context or {}
            )

    async def retrieve_memories(self, user_id: str, query: str = None, limit: int = 5) -> List[Dict]:
        """Retrieve relevant memories"""
        # Currently simple retrieval, ideally vector search here too
        if not db.pool:
            return []
            
        async with db.pool.acquire() as conn:
            # Simple recent memories
            rows = await conn.fetch(
                "SELECT * FROM memories WHERE user_id = $1 ORDER BY created_at DESC LIMIT $2",
                user_id, limit
            )
            return [dict(row) for row in rows]

memory_service = MemoryService()
