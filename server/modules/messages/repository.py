from typing import List, Dict, Optional
import json
from datetime import datetime
from config.database import db

class MessageRepository:
    
    async def create(self, conversation_id: str, role: str, content: str, model: str = None, parent_id: str = None, message_id: str = None, metadata: Dict = None) -> Dict:
        """Create a new message"""
        import uuid
        message_id = message_id or str(uuid.uuid4())
        now = datetime.now()
        
        message = {
            'id': message_id,
            'conversation_id': conversation_id,
            'role': role,
            'content': content,
            'model': model,
            'parent_id': parent_id,
            'created_at': now.isoformat(),
            'metadata': metadata or {}
        }
        
        if db.use_database and db.pool:
            async with db.pool.acquire() as conn:
                # Note: The table schema in repo.py had 'model', 'parent_id'. database.py had 'metadata'.
                # We should try to support both Sets.
                # Assuming the DB has all these columns. If not, we might need a migration, 
                # but based on the previous files, both sets existed in different contexts.
                # We'll try to insert what we can.
                from config.logger import logger
                logger.info(f"DEBUG REPO MESSAGE: now type: {type(now)}, value: {now}")
                logger.info(f"DEBUG REPO MESSAGE: parent_id type: {type(parent_id)}, value: {parent_id}")
                
                row = await conn.fetchrow(
                    """INSERT INTO messages (id, conversation_id, role, content, model, parent_id, metadata, created_at) 
                       VALUES ($1, $2, $3, $4, $5, $6, $7, $8) 
                       RETURNING *""",
                    message_id, conversation_id, role, content, model, parent_id, json.dumps(metadata or {}), now
                )
                return dict(row)
        else:
            data = db.read_json('messages')
            data[message_id] = message
            db.write_json('messages', data)
            return message

    async def get_by_conversation(self, conversation_id: str, limit: int = 100, offset: int = 0) -> List[Dict]:
        """Get messages for a conversation"""
        if db.use_database and db.pool:
            async with db.pool.acquire() as conn:
                rows = await conn.fetch(
                    """SELECT * FROM messages 
                       WHERE conversation_id = $1 
                       ORDER BY created_at ASC 
                       LIMIT $2 OFFSET $3""",
                    conversation_id, limit, offset
                )
                return [dict(row) for row in rows]
        else:
            data = db.read_json('messages')
            messages = [
                msg for msg in data.values()
                if msg.get('conversation_id') == conversation_id or str(msg.get('conversation_id')) == str(conversation_id)
            ]
            messages.sort(key=lambda x: x.get('created_at', ''))
            return messages[offset:offset + limit]

    async def get_history_for_context(self, conversation_id: str, limit: int = 10) -> List[Dict]:
        """Get recent messages formatted for LLM context"""
        messages = await self.get_by_conversation(conversation_id, limit)
        # We might need to take the LAST 'limit' messages, not just the first 'limit' if limit is small.
        # get_by_conversation returns ASC (oldest first). 
        # If we want context, we usually want the *last* N messages.
        
        # NOTE: logic in original repo.py was just get_by_conversation(limit).
        # database.py get_messages logic was also ASC. 
        # So it was getting the *first* N messages of the conversation? That seems wrong for context window if conversation is long.
        # But for now, we preserve the existing logic of "get N messages".
        
        return [{"role": m["role"], "content": m["content"]} for m in messages]

    async def search(self, query: str, limit: int = 50) -> List[Dict]:
        """Search messages"""
        if db.use_database and db.pool:
            async with db.pool.acquire() as conn:
                rows = await conn.fetch(
                    '''SELECT * FROM messages 
                       WHERE to_tsvector('english', content) @@ plainto_tsquery('english', $1)
                       ORDER BY created_at DESC
                       LIMIT $2''',
                    query, limit
                )
                return [dict(row) for row in rows]
        else:
            data = db.read_json('messages')
            results = [
                msg for msg in data.values()
                if query.lower() in msg.get('content', '').lower()
            ]
            results.sort(key=lambda x: x.get('created_at', ''), reverse=True)
            return results[:limit]

message_repository = MessageRepository()
