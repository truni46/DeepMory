import asyncio
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config.database import db
from config.logger import logger

async def check_schema():
    await db.connect()
    try:
        if db.pool:
            async with db.pool.acquire() as conn:
                rows = await conn.fetch(
                    "SELECT column_name, data_type FROM information_schema.columns WHERE table_name = 'conversations'"
                )
                print("Columns in conversations table:")
                for row in rows:
                    print(f"- {row['column_name']} ({row['data_type']})")
    finally:
        await db.close()

if __name__ == "__main__":
    asyncio.run(check_schema())
