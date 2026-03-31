import asyncio
from pathlib import Path
from config.database import db

async def migrate():
    await db.connect()
    p = Path(__file__).parent / 'migrations' / '004_agent_memory_history.sql'
    sql = p.read_text('utf-8')
    if db.pool:
        async with db.pool.acquire() as conn:
            await conn.execute(sql)
            print("Migration 004 applied")
    await db.close()

if __name__ == '__main__':
    asyncio.run(migrate())
