import os
import json
from pathlib import Path
from typing import Optional, Dict, Any, List
from dotenv import load_dotenv
from config.logger import logger
import asyncio

load_dotenv()


class Database:
    """Database manager with PostgreSQL and JSON fallback support"""
    
    def __init__(self):
        self.useDatabase = os.getenv('USE_DATABASE', 'false').lower() == 'true'
        self.pool = None
        # Move up from config -> server -> root -> data
        self.data_dir = Path(__file__).parent.parent.parent / 'data'
        self.data_dir.mkdir(exist_ok=True)
        
        # Database configuration
        self.db_config = {
            'host': os.getenv('DB_HOST', 'localhost'),
            'port': int(os.getenv('DB_PORT', 5432)),
            'database': os.getenv('DB_NAME', 'deepmory_db'),
            'user': os.getenv('DB_USER', 'deepmory'),
            'password': os.getenv('DB_PASSWORD', ''),
        }
    
    async def connect(self):
        """Connect to PostgreSQL database"""
        if not self.useDatabase:
            logger.info("Database disabled, using JSON file storage")
            return
        
        try:
            import asyncpg
            # Create connection pool
            self.pool = await asyncpg.create_pool(**self.db_config)
            logger.info("Database connected successfully")
        except Exception as e:
            logger.error(f"Failed to connect to database: {e}")
            logger.warning("Falling back to JSON file storage")
            self.useDatabase = False
            self.pool = None
    
    async def close(self):
        """Close database connection"""
        if self.pool:
            await self.pool.close()
            logger.info("Database connection closed")
    
    async def check_connection(self) -> bool:
        """Check if database is connected"""
        if not self.useDatabase or not self.pool:
            return False
        
        try:
            async with self.pool.acquire() as conn:
                await conn.execute('SELECT 1')
            return True
        except Exception as e:
            logger.error(f"Database connection check failed: {e}")
            return False
    
    def get_json_file(self, name: str) -> Path:
        """Get path to JSON file"""
        return self.data_dir / f'{name}.json'
    
    def read_json(self, name: str) -> Any:
        """Read data from JSON file"""
        file_path = self.get_json_file(name)
        if file_path.exists():
            with open(file_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        return {}
    
    def write_json(self, name: str, data: Any):
        """Write data to JSON file"""
        file_path = self.get_json_file(name)
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
    

# Global database instance
db = Database()
