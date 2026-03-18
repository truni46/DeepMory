from typing import List, Dict, Optional
import json
from datetime import datetime
from config.database import db

class ConversationRepository:
    
    async def create(self, userId: str, title: str = None, projectId: str = None) -> Dict:
        """Create a new conversation"""
        import uuid
        conversationId = str(uuid.uuid4())
        title = title or "New Conversation"
        now = datetime.now()
        
        conversation = {
            'id': conversationId,
            'userId': userId,
            'projectId': projectId,
            'title': title,
            'createdAt': now.isoformat(),
            'updatedAt': now.isoformat(),
            'metadata': {}
        }

        if db.useDatabase and db.pool:
            async with db.pool.acquire() as conn:
                row = await conn.fetchrow(
                    """INSERT INTO conversations (id, "userId", "projectId", title, metadata, "createdAt", "updatedAt") 
                       VALUES ($1, $2, $3, $4, $5, $6, $7) 
                       RETURNING *""",
                    conversationId, userId, projectId, title, json.dumps({}), now, now
                )
                return dict(row)
        else:
            data = db.read_json('conversations')
            data[conversationId] = conversation
            db.write_json('conversations', data)
            return conversation

    async def getByUser(self, userId: str) -> List[Dict]:
        """Get conversations for a user"""
        if db.useDatabase and db.pool:
            async with db.pool.acquire() as conn:
                rows = await conn.fetch(
                    """SELECT * FROM conversations WHERE "userId" = $1 ORDER BY "updatedAt" DESC""", 
                    userId
                )
                return [dict(row) for row in rows]
        else:
            data = db.read_json('conversations')
            userConvs = [
                c for c in data.values() 
                if c.get('userId') == userId or str(c.get('userId')) == str(userId)
            ]
            userConvs.sort(key=lambda x: x.get('updatedAt', ''), reverse=True)
            return userConvs

    async def getById(self, conversationId: str, userId: str) -> Optional[Dict]:
        """Get conversation by ID and verify user ownership"""
        if db.useDatabase and db.pool:
            async with db.pool.acquire() as conn:
                row = await conn.fetchrow(
                    """SELECT * FROM conversations WHERE id = $1 AND "userId" = $2""",
                    conversationId, userId
                )
                return dict(row) if row else None
        else:
            data = db.read_json('conversations')
            conv = data.get(conversationId)
            if conv and (str(conv.get('userId')) == str(userId)):
                return conv
            return None

    async def update(self, conversationId: str, userId: str, updates: Dict) -> Optional[Dict]:
        """Update a conversation"""
        now = datetime.now()
        
        if db.useDatabase and db.pool:
            async with db.pool.acquire() as conn:
                setClauses = []
                values = []
                paramCount = 1
                
                for key, value in updates.items():
                    setClauses.append(f'"{key}" = ${paramCount}')
                    if isinstance(value, (dict, list)):
                        values.append(json.dumps(value))
                    else:
                        values.append(value)
                    paramCount += 1
                
                if not setClauses:
                    return await self.getById(conversationId, userId)

                setClauses.append(f'"updatedAt" = ${paramCount}')
                values.append(now)
                paramCount += 1
                
                values.append(conversationId)
                values.append(userId)
                
                query = f"""
                    UPDATE conversations 
                    SET {', '.join(setClauses)}
                    WHERE id = ${paramCount} AND "userId" = ${paramCount + 1}
                    RETURNING *
                """
                
                row = await conn.fetchrow(query, *values)
                return dict(row) if row else None
        else:
            data = db.read_json('conversations')
            if conversationId in data:
                conv = data[conversationId]
                if str(conv.get('userId')) == str(userId):
                    conv.update(updates)
                    conv['updatedAt'] = now.isoformat()
                    db.write_json('conversations', data)
                    return conv
            return None

    async def delete(self, conversationId: str, userId: str) -> bool:
        """Delete a conversation"""
        if db.useDatabase and db.pool:
            async with db.pool.acquire() as conn:
                await conn.execute(
                    """DELETE FROM messages WHERE "conversationId" = $1""",
                    conversationId
                )
                result = await conn.execute(
                    """DELETE FROM conversations WHERE id = $1 AND "userId" = $2""",
                    conversationId, userId
                )
                return result == "DELETE 1"
        else:
            data = db.read_json('conversations')
            if conversationId in data:
                conv = data[conversationId]
                if str(conv.get('userId')) == str(userId):
                    del data[conversationId]
                    db.write_json('conversations', data)
                    
                    messagesData = db.read_json('messages')
                    messagesData = {
                        k: v for k, v in messagesData.items()
                        if v.get('conversationId') != conversationId
                    }
                    db.write_json('messages', messagesData)
                    return True
            return False
            
conversationRepository = ConversationRepository()
