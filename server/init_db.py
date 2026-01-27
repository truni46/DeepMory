import asyncio
import os
from pathlib import Path
from config.database import db

async def init_db():
    print("Connecting to database...")
    await db.connect()
    
    if not db.use_database:
        print("Database not enabled or connection failed.")
        return

    schema_path = Path(__file__).parent / 'migrations' / 'schema.sql'
    if not schema_path.exists():
        print(f"Schema file not found at {schema_path}")
        return

    print("Reading schema...")
    with open(schema_path, 'r') as f:
        schema_sql = f.read()

    print("Executing schema...")
    try:
        if db.pool:
            async with db.pool.acquire() as conn:
                await conn.execute(schema_sql)
        print("Schema initialized successfully!")
    except Exception as e:
        print(f"Error initializing schema: {e}")
    finally:
        await db.close()

if __name__ == "__main__":
    asyncio.run(init_db())
