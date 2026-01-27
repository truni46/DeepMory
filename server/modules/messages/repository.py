from typing import List, Dict, Optional
from config.database import db

class MessageRepository:
    
    async def create(self, conversation_id: str, role: str, content: str, model: str = None, parent_id: str = None) -> Dict:
        async with db.pool.acquire() as conn:
            row = await conn.fetchrow(
                """INSERT INTO messages (conversation_id, role, content, model, parent_id) 
                   VALUES ($1, $2, $3, $4, $5) 
                   RETURNING *""",
                conversation_id, role, content, model, parent_id
            )
            return dict(row)

    async def get_by_conversation(self, conversation_id: str, limit: int = 100) -> List[Dict]:
        async with db.pool.acquire() as conn:
            rows = await conn.fetch(
                """SELECT * FROM messages 
                   WHERE conversation_id = $1 
                   ORDER BY created_at ASC 
                   LIMIT $2""",
                conversation_id, limit
            )
            return [dict(row) for row in rows]
            
    async def get_history_for_context(self, conversation_id: str, limit: int = 10) -> List[Dict]:
        """Get recent messages formatted for LLM context"""
        messages = await self.get_by_conversation(conversation_id, limit)
        return [{"role": m["role"], "content": m["content"]} for m in messages]

message_repository = MessageRepository()
