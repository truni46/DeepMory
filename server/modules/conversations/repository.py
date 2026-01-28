from typing import List, Dict, Optional
import json
from datetime import datetime
from config.database import db

class ConversationRepository:
    
    async def create(self, user_id: str, title: str = None, project_id: str = None) -> Dict:
        """Create a new conversation"""
        import uuid
        conversation_id = str(uuid.uuid4())
        title = title or "New Conversation"
        now = datetime.now()
        
        conversation = {
            'id': conversation_id,
            'user_id': user_id,
            'project_id': project_id,
            'title': title,
            'created_at': now.isoformat(),
            'updated_at': now.isoformat(),
            'metadata': {}
        }

        if db.use_database and db.pool:
            async with db.pool.acquire() as conn:
                # Assuming user_id column exists based on previous repository.py content
                # Note: database.py didn't use user_id, but repository.py did. 
                # We should reconcile this. The current schema likely has user_id.
                from config.logger import logger
                logger.info(f"DEBUG REPO CONVERSATION: created_at type: {type(now)}, value: {now}")
                
                row = await conn.fetchrow(
                    """INSERT INTO conversations (id, user_id, project_id, title, metadata, created_at, updated_at) 
                       VALUES ($1, $2, $3, $4, $5, $6, $7) 
                       RETURNING *""",
                    conversation_id, user_id, project_id, title, json.dumps({}), now, now
                )
                return dict(row)
        else:
            data = db.read_json('conversations')
            data[conversation_id] = conversation
            db.write_json('conversations', data)
            return conversation

    async def get_by_user(self, user_id: str) -> List[Dict]:
        """Get conversations for a user"""
        if db.use_database and db.pool:
            async with db.pool.acquire() as conn:
                rows = await conn.fetch(
                    "SELECT * FROM conversations WHERE user_id = $1 ORDER BY updated_at DESC", 
                    user_id
                )
                return [dict(row) for row in rows]
        else:
            data = db.read_json('conversations')
            # Filter by user_id if present in JSON data
            user_convs = [
                c for c in data.values() 
                if c.get('user_id') == user_id or str(c.get('user_id')) == str(user_id)
            ]
            # Sort by updated_at descending
            user_convs.sort(key=lambda x: x.get('updated_at', ''), reverse=True)
            return user_convs

    async def get_by_id(self, conversation_id: str, user_id: str) -> Optional[Dict]:
        """Get conversation by ID and verify user ownership"""
        if db.use_database and db.pool:
            async with db.pool.acquire() as conn:
                row = await conn.fetchrow(
                    "SELECT * FROM conversations WHERE id = $1 AND user_id = $2",
                    conversation_id, user_id
                )
                return dict(row) if row else None
        else:
            data = db.read_json('conversations')
            conv = data.get(conversation_id)
            if conv and (str(conv.get('user_id')) == str(user_id)):
                return conv
            return None

    async def update(self, conversation_id: str, user_id: str, updates: Dict) -> Optional[Dict]:
        """Update a conversation"""
        now = datetime.now()
        
        if db.use_database and db.pool:
            async with db.pool.acquire() as conn:
                set_clauses = []
                values = []
                param_count = 1
                
                for key, value in updates.items():
                    set_clauses.append(f"{key} = ${param_count}")
                    if isinstance(value, (dict, list)):
                        values.append(json.dumps(value))
                    else:
                        values.append(value)
                    param_count += 1
                
                if not set_clauses:
                    return await self.get_by_id(conversation_id, user_id)

                set_clauses.append(f"updated_at = ${param_count}")
                values.append(now)
                param_count += 1
                
                values.append(conversation_id)
                values.append(user_id)
                
                query = f"""
                    UPDATE conversations 
                    SET {', '.join(set_clauses)}
                    WHERE id = ${param_count} AND user_id = ${param_count + 1}
                    RETURNING *
                """
                
                row = await conn.fetchrow(query, *values)
                return dict(row) if row else None
        else:
            data = db.read_json('conversations')
            if conversation_id in data:
                conv = data[conversation_id]
                if str(conv.get('user_id')) == str(user_id):
                    conv.update(updates)
                    conv['updated_at'] = now.isoformat()
                    db.write_json('conversations', data)
                    return conv
            return None

    async def delete(self, conversation_id: str, user_id: str) -> bool:
        """Delete a conversation"""
        if db.use_database and db.pool:
            async with db.pool.acquire() as conn:
                # Delete messages first
                await conn.execute("DELETE FROM messages WHERE conversation_id = $1", conversation_id)
                
                result = await conn.execute(
                    "DELETE FROM conversations WHERE id = $1 AND user_id = $2",
                    conversation_id, user_id
                )
                return result == "DELETE 1"
        else:
            data = db.read_json('conversations')
            if conversation_id in data:
                conv = data[conversation_id]
                if str(conv.get('user_id')) == str(user_id):
                    del data[conversation_id]
                    db.write_json('conversations', data)
                    
                    # Also delete messages
                    messages_data = db.read_json('messages')
                    messages_data = {
                        k: v for k, v in messages_data.items()
                        if v.get('conversation_id') != conversation_id
                    }
                    db.write_json('messages', messages_data)
                    return True
            return False
            
conversation_repository = ConversationRepository()
