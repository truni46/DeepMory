from typing import List, Dict, Optional
from config.database import db

class ConversationRepository:
    
    async def create(self, user_id: str, title: str = None, project_id: str = None) -> Dict:
        async with db.pool.acquire() as conn:
            row = await conn.fetchrow(
                """INSERT INTO conversations (user_id, project_id, title) 
                   VALUES ($1, $2, $3) 
                   RETURNING *""",
                user_id, project_id, title or "New Conversation"
            )
            return dict(row)

    async def get_by_user(self, user_id: str) -> List[Dict]:
        async with db.pool.acquire() as conn:
            rows = await conn.fetch(
                "SELECT * FROM conversations WHERE user_id = $1 ORDER BY updated_at DESC", 
                user_id
            )
            return [dict(row) for row in rows]

    async def get_by_id(self, conversation_id: str, user_id: str) -> Optional[Dict]:
        async with db.pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT * FROM conversations WHERE id = $1 AND user_id = $2",
                conversation_id, user_id
            )
            return dict(row) if row else None

    async def update(self, conversation_id: str, user_id: str, updates: Dict) -> Optional[Dict]:
        async with db.pool.acquire() as conn:
            set_clauses = []
            values = []
            param_count = 1
            
            for key, value in updates.items():
                set_clauses.append(f"{key} = ${param_count}")
                values.append(value)
                param_count += 1
            
            if not set_clauses:
                return await self.get_by_id(conversation_id, user_id)

            values.append(conversation_id)
            values.append(user_id)
            
            query = f"""
                UPDATE conversations 
                SET {', '.join(set_clauses)}, updated_at = NOW()
                WHERE id = ${param_count} AND user_id = ${param_count + 1}
                RETURNING *
            """
            
            row = await conn.fetchrow(query, *values)
            row = await conn.fetchrow(query, *values)
            return dict(row) if row else None

    async def delete(self, conversation_id: str, user_id: str) -> bool:
        async with db.pool.acquire() as conn:
            # Delete messages first (cascade usually handles this but manual is safer without FKs)
            await conn.execute("DELETE FROM messages WHERE conversation_id = $1", conversation_id)
            
            result = await conn.execute(
                "DELETE FROM conversations WHERE id = $1 AND user_id = $2",
                conversation_id, user_id
            )
            return result == "DELETE 1"
            
conversation_repository = ConversationRepository()
