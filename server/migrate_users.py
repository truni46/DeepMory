import asyncio
from config.database import db
from config.logger import logger

async def migrate_db():
    await db.connect()
    try:
        if db.pool:
            async with db.pool.acquire() as conn:
                logger.info("Checking for full_name column...")
                # Check if column exists
                row = await conn.fetchrow(
                    "SELECT column_name FROM information_schema.columns WHERE table_name = 'users' AND column_name = 'full_name'"
                )
                if not row:
                    logger.info("Adding full_name column to users table...")
                    await conn.execute("ALTER TABLE users ADD COLUMN full_name VARCHAR(255)")
                    logger.info("Column added successfully.")
                else:
                    logger.info("Column full_name already exists.")
    except Exception as e:
        logger.error(f"Migration error: {e}")
    finally:
        await db.close()

if __name__ == "__main__":
    asyncio.run(migrate_db())
