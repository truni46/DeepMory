import os
import re
import json
from pathlib import Path
from typing import Optional, Dict, Any, List
from dotenv import load_dotenv
from config.logger import logger
import asyncio

load_dotenv()

MIGRATIONS_DIR = Path(__file__).parent.parent / "migrations"


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
            self.pool = await asyncpg.create_pool(**self.db_config)
            logger.info("Database connected successfully")
            await self._runMigrations()
        except Exception as e:
            logger.error(f"Failed to connect to database: {e}")
            logger.warning("Falling back to JSON file storage")
            self.useDatabase = False
            self.pool = None

    async def _runMigrations(self):
        if not self.pool:
            return
        try:
            async with self.pool.acquire() as conn:
                await conn.execute("""
                    CREATE TABLE IF NOT EXISTS _migrations (
                        name VARCHAR(255) PRIMARY KEY,
                        "appliedAt" TIMESTAMPTZ DEFAULT now()
                    )
                """)
                applied = {r["name"] for r in await conn.fetch('SELECT name FROM _migrations')}

                files = sorted(
                    f for f in MIGRATIONS_DIR.glob("*.sql")
                    if re.match(r"^\d{3}_", f.name) and f.name not in applied
                )
                for f in files:
                    sql = f.read_text(encoding="utf-8")
                    logger.info(f"Applying migration {f.name} ...")
                    await conn.execute(sql)
                    await conn.execute(
                        'INSERT INTO _migrations (name) VALUES ($1)', f.name
                    )
                    logger.info(f"Migration {f.name} applied")
        except Exception as e:
            logger.error(f"_runMigrations failed: {e}")
    
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
