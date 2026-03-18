from typing import List, Dict, Optional
import json
from datetime import datetime
from config.database import db

class MessageRepository:
    
    async def create(self, conversationId: str, role: str, content: str, model: str = None, parentId: str = None, messageId: str = None, metadata: Dict = None) -> Dict:
        """Create a new message"""
        import uuid
        messageId = messageId or str(uuid.uuid4())
        now = datetime.now()
        
        message = {
            'id': messageId,
            'conversationId': conversationId,
            'role': role,
            'content': content,
            'model': model,
            'parentId': parentId,
            'createdAt': now.isoformat(),
            'metadata': metadata or {}
        }
        
        if db.useDatabase and db.pool:
            async with db.pool.acquire() as conn:
                row = await conn.fetchrow(
                    """INSERT INTO messages (id, "conversationId", role, content, model, "parentId", metadata, "createdAt") 
                       VALUES ($1, $2, $3, $4, $5, $6, $7, $8) 
                       RETURNING *""",
                    messageId, conversationId, role, content, model, parentId, json.dumps(metadata or {}), now
                )
                return dict(row)
        else:
            data = db.read_json('messages')
            data[messageId] = message
            db.write_json('messages', data)
            return message

    async def getByConversation(self, conversationId: str, limit: int = 100, offset: int = 0) -> List[Dict]:
        """Get messages for a conversation"""
        if db.useDatabase and db.pool:
            async with db.pool.acquire() as conn:
                rows = await conn.fetch(
                    """SELECT * FROM messages 
                       WHERE "conversationId" = $1 
                       ORDER BY "createdAt" ASC 
                       LIMIT $2 OFFSET $3""",
                    conversationId, limit, offset
                )
                return [dict(row) for row in rows]
        else:
            data = db.read_json('messages')
            messages = [
                msg for msg in data.values()
                if msg.get('conversationId') == conversationId or str(msg.get('conversationId')) == str(conversationId)
            ]
            messages.sort(key=lambda x: x.get('createdAt', ''))
            return messages[offset:offset + limit]        
        
    async def getHistoryForContext(self, conversationId: str, limit: int = 10) -> List[Dict]:
        """Get recent messages formatted for LLM context"""
        messages = await self.getByConversation(conversationId, limit)
        return [{"role": m["role"], "content": m["content"]} for m in messages]

    async def search(self, query: str, limit: int = 50) -> List[Dict]:
        """Search messages"""
        if db.useDatabase and db.pool:
            async with db.pool.acquire() as conn:
                rows = await conn.fetch(
                    '''SELECT * FROM messages 
                       WHERE to_tsvector('english', content) @@ plainto_tsquery('english', $1)
                       ORDER BY "createdAt" DESC
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
            results.sort(key=lambda x: x.get('createdAt', ''), reverse=True)
            return results[:limit]

messageRepository = MessageRepository()
