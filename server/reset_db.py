import asyncio
from config.database import db
from config.logger import logger

async def reset_db():
    await db.connect()
    try:
        if db.pool:
            async with db.pool.acquire() as conn:
                logger.info("Dropping tables...")
                await conn.execute("DROP TABLE IF EXISTS messages CASCADE")
                await conn.execute("DROP TABLE IF EXISTS conversations CASCADE")
                await conn.execute("DROP TABLE IF EXISTS documents CASCADE")
                await conn.execute("DROP TABLE IF EXISTS projects CASCADE")
                await conn.execute("DROP TABLE IF EXISTS memories CASCADE")
                await conn.execute("DROP TABLE IF EXISTS mcp_servers CASCADE")
                await conn.execute("DROP TABLE IF EXISTS settings CASCADE")
                await conn.execute("DROP TABLE IF EXISTS users CASCADE")
                logger.info("Tables dropped successfully.")
    except Exception as e:
        logger.error(f"Error dropping tables: {e}")
    finally:
        await db.close()

if __name__ == "__main__":
    asyncio.run(reset_db())
