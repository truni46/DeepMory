import asyncio
import asyncpg
import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()


async def run_migration():
    """Run database migration"""
    print("Running database migration...")
    
    # Database configuration
    db_config = {
        'host': os.getenv('DB_HOST', 'localhost'),
        'port': int(os.getenv('DB_PORT', 5432)),
        'database': os.getenv('DB_NAME', 'ai_tutor_db'),
        'user': os.getenv('DB_USER', 'ai_tutor'),
        'password': os.getenv('DB_PASSWORD', ''),
    }
    
    try:
        # Connect to database
        conn = await asyncpg.connect(**db_config)
        print(f"Connected to database: {db_config['database']}")
        
        # Read migration SQL file
        migration_file = Path(__file__).parent / '001_initial_schema.sql'
        
        if not migration_file.exists():
            # Try parent directory (server folder)
            migration_file = Path(__file__).parent.parent.parent / 'server' / 'migrations' / '001_initial_schema.sql'
        
        if not migration_file.exists():
            print("Migration file not found!")
            return
        
        with open(migration_file, 'r', encoding='utf-8') as f:
            sql = f.read()
        
        print(f"Running migration from: {migration_file.name}")
        
        # Execute migration
        await conn.execute(sql)
        
        print("Migration completed successfully!")
        
        # Close connection
        await conn.close()
        
    except Exception as e:
        print(f"Migration failed: {e}")
        raise


if __name__ == "__main__":
    asyncio.run(run_migration())
