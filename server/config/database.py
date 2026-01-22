import os
import json
import psycopg2
from psycopg2 import pool
from pathlib import Path
from typing import Optional, Dict, Any, List
from dotenv import load_dotenv
from config.logger import logger
import asyncio

load_dotenv()


class Database:
    """Database manager with PostgreSQL and JSON fallback support"""
    
    def __init__(self):
        self.use_database = os.getenv('USE_DATABASE', 'false').lower() == 'true'
        self.pool: Optional[pool.SimpleConnectionPool] = None
        self.data_dir = Path(__file__).parent.parent / 'data'
        self.data_dir.mkdir(exist_ok=True)
        
        # Database configuration
        self.db_config = {
            'host': os.getenv('DB_HOST', 'localhost'),
            'port': int(os.getenv('DB_PORT', 5432)),
            'database': os.getenv('DB_NAME', 'ai_tutor_db'),
            'user': os.getenv('DB_USER', 'ai_tutor'),
            'password': os.getenv('DB_PASSWORD', ''),
        }
    
    async def connect(self):
        """Connect to PostgreSQL database"""
        if not self.use_database:
            logger.info("Database disabled, using JSON file storage")
            return
        
        try:
            # Create connection pool
            self.pool = psycopg2.pool.SimpleConnectionPool(
                2, 10,  # min and max connections
                **self.db_config
            )
            logger.info("Database connected successfully")
        except Exception as e:
            logger.error(f"Failed to connect to database: {e}")
            logger.warning("Falling back to JSON file storage")
            self.use_database = False
    
    async def close(self):
        """Close database connection"""
        if self.pool:
            self.pool.closeall()
            logger.info("Database connection closed")
    
    async def check_connection(self) -> bool:
        """Check if database is connected"""
        if not self.use_database or not self.pool:
            return False
        
        try:
            conn = self.pool.getconn()
            cur = conn.cursor()
            cur.execute('SELECT 1')
            cur.close()
            self.pool.putconn(conn)
            return True
        except Exception as e:
            logger.error(f"Database connection check failed: {e}")
            return False
    
    # ========== JSON File Storage Methods ==========
    
    def _get_json_file(self, name: str) -> Path:
        """Get path to JSON file"""
        return self.data_dir / f'{name}.json'
    
    def _read_json(self, name: str) -> Any:
        """Read data from JSON file"""
        file_path = self._get_json_file(name)
        if file_path.exists():
            with open(file_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        return {}
    
    def _write_json(self, name: str, data: Any):
        """Write data to JSON file"""
        file_path = self._get_json_file(name)
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
    
    # ========== Conversation Methods ==========
    
    async def get_all_conversations(self) -> List[Dict]:
        """Get all conversations"""
        if self.use_database and self.pool:
            async with self.pool.acquire() as conn:
                rows = await conn.fetch(
                    'SELECT * FROM conversations ORDER BY created_at DESC'
                )
                return [dict(row) for row in rows]
        else:
            data = self._read_json('conversations')
            return list(data.values())
    
    async def get_conversation_by_id(self, conversation_id: str) -> Optional[Dict]:
        """Get conversation by ID"""
        if self.use_database and self.pool:
            async with self.pool.acquire() as conn:
                row = await conn.fetchrow(
                    'SELECT * FROM conversations WHERE id = $1',
                    conversation_id
                )
                return dict(row) if row else None
        else:
            data = self._read_json('conversations')
            return data.get(conversation_id)
    
    async def create_conversation(self, conversation_id: str, title: str, metadata: Dict = None) -> Dict:
        """Create new conversation"""
        from datetime import datetime
        
        conversation = {
            'id': conversation_id,
            'title': title,
            'created_at': datetime.now().isoformat(),
            'updated_at': datetime.now().isoformat(),
            'metadata': metadata or {}
        }
        
        if self.use_database and self.pool:
            async with self.pool.acquire() as conn:
                await conn.execute(
                    '''INSERT INTO conversations (id, title, metadata, created_at, updated_at)
                       VALUES ($1, $2, $3, $4, $5)''',
                    conversation_id, title, json.dumps(metadata or {}),
                    conversation['created_at'], conversation['updated_at']
                )
        else:
            data = self._read_json('conversations')
            data[conversation_id] = conversation
            self._write_json('conversations', data)
        
        return conversation
    
    async def update_conversation(self, conversation_id: str, updates: Dict) -> Optional[Dict]:
        """Update conversation"""
        from datetime import datetime
        
        if self.use_database and self.pool:
            async with self.pool.acquire() as conn:
                set_clauses = []
                values = []
                param_count = 1
                
                if 'title' in updates:
                    set_clauses.append(f'title = ${param_count}')
                    values.append(updates['title'])
                    param_count += 1
                
                if 'metadata' in updates:
                    set_clauses.append(f'metadata = ${param_count}')
                    values.append(json.dumps(updates['metadata']))
                    param_count += 1
                
                set_clauses.append(f'updated_at = ${param_count}')
                values.append(datetime.now().isoformat())
                param_count += 1
                
                values.append(conversation_id)
                
                query = f'''UPDATE conversations 
                           SET {', '.join(set_clauses)}
                           WHERE id = ${param_count}
                           RETURNING *'''
                
                row = await conn.fetchrow(query, *values)
                return dict(row) if row else None
        else:
            data = self._read_json('conversations')
            if conversation_id in data:
                data[conversation_id].update(updates)
                data[conversation_id]['updated_at'] = datetime.now().isoformat()
                self._write_json('conversations', data)
                return data[conversation_id]
            return None
    
    async def delete_conversation(self, conversation_id: str) -> bool:
        """Delete conversation"""
        if self.use_database and self.pool:
            async with self.pool.acquire() as conn:
                result = await conn.execute(
                    'DELETE FROM conversations WHERE id = $1',
                    conversation_id
                )
                return result == 'DELETE 1'
        else:
            data = self._read_json('conversations')
            if conversation_id in data:
                del data[conversation_id]
                self._write_json('conversations', data)
                
                # Also delete messages
                messages_data = self._read_json('messages')
                messages_data = {
                    k: v for k, v in messages_data.items()
                    if v.get('conversation_id') != conversation_id
                }
                self._write_json('messages', messages_data)
                return True
            return False
    
    # ========== Message Methods ==========
    
    async def get_messages(self, conversation_id: str, limit: int = 100, offset: int = 0) -> List[Dict]:
        """Get messages for a conversation"""
        if self.use_database and self.pool:
            async with self.pool.acquire() as conn:
                rows = await conn.fetch(
                    '''SELECT * FROM messages 
                       WHERE conversation_id = $1 
                       ORDER BY created_at ASC
                       LIMIT $2 OFFSET $3''',
                    conversation_id, limit, offset
                )
                return [dict(row) for row in rows]
        else:
            data = self._read_json('messages')
            messages = [
                msg for msg in data.values()
                if msg.get('conversation_id') == conversation_id
            ]
            messages.sort(key=lambda x: x.get('created_at', ''))
            return messages[offset:offset + limit]
    
    async def save_message(self, message_id: str, conversation_id: str, role: str, content: str, metadata: Dict = None) -> Dict:
        """Save a message"""
        from datetime import datetime
        
        message = {
            'id': message_id,
            'conversation_id': conversation_id,
            'role': role,
            'content': content,
            'created_at': datetime.now().isoformat(),
            'metadata': metadata or {}
        }
        
        if self.use_database and self.pool:
            async with self.pool.acquire() as conn:
                await conn.execute(
                    '''INSERT INTO messages (id, conversation_id, role, content, metadata, created_at)
                       VALUES ($1, $2, $3, $4, $5, $6)''',
                    message_id, conversation_id, role, content,
                    json.dumps(metadata or {}), message['created_at']
                )
        else:
            data = self._read_json('messages')
            data[message_id] = message
            self._write_json('messages', data)
        
        return message
    
    async def search_messages(self, query: str, limit: int = 50) -> List[Dict]:
        """Search messages"""
        if self.use_database and self.pool:
            async with self.pool.acquire() as conn:
                rows = await conn.fetch(
                    '''SELECT * FROM messages 
                       WHERE to_tsvector('english', content) @@ plainto_tsquery('english', $1)
                       ORDER BY created_at DESC
                       LIMIT $2''',
                    query, limit
                )
                return [dict(row) for row in rows]
        else:
            data = self._read_json('messages')
            results = [
                msg for msg in data.values()
                if query.lower() in msg.get('content', '').lower()
            ]
            results.sort(key=lambda x: x.get('created_at', ''), reverse=True)
            return results[:limit]
    
    # ========== Settings Methods ==========
    
    async def get_settings(self) -> Dict:
        """Get all settings"""
        if self.use_database and self.pool:
            async with self.pool.acquire() as conn:
                rows = await conn.fetch('SELECT key, value FROM settings')
                settings = {}
                for row in rows:
                    settings[row['key']] = json.loads(row['value']) if isinstance(row['value'], str) else row['value']
                return settings
        else:
            return self._read_json('settings')
    
    async def update_setting(self, key: str, value: Any):
        """Update a setting"""
        from datetime import datetime
        
        if self.use_database and self.pool:
            async with self.pool.acquire() as conn:
                await conn.execute(
                    '''INSERT INTO settings (key, value, updated_at)
                       VALUES ($1, $2, $3)
                       ON CONFLICT (key) DO UPDATE
                       SET value = $2, updated_at = $3''',
                    key, json.dumps(value), datetime.now().isoformat()
                )
        else:
            data = self._read_json('settings')
            data[key] = value
            self._write_json('settings', data)


# Global database instance
db = Database()
