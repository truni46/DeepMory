import asyncio
import asyncpg
import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv(dotenv_path=str(Path(__file__).parent.parent / ".env"))


async def runMigration():
    """Run all pending database migrations in numeric order."""
    print("Running database migrations...")
    dbConfig = {
        "host": os.getenv("DB_HOST", "localhost"),
        "port": int(os.getenv("DB_PORT", 5432)),
        "database": os.getenv("DB_NAME", "deepmory"),
        "user": os.getenv("DB_USER", "admin"),
        "password": os.getenv("DB_PASSWORD", ""),
    }
    try:
        conn = await asyncpg.connect(**dbConfig)
        print(f"Connected to database: {dbConfig['database']}")

        migrationDir = Path(__file__).parent
        sqlFiles = sorted(migrationDir.glob("[0-9][0-9][0-9]_*.sql"))

        for sqlFile in sqlFiles:
            print(f"Running: {sqlFile.name}")
            sql = sqlFile.read_text(encoding="utf-8")
            try:
                await conn.execute(sql)
                print(f"  OK: {sqlFile.name}")
            except Exception as e:
                print(f"  WARN: {sqlFile.name} — {e} (may already exist, continuing)")

        await conn.close()
        print("Migrations completed.")
    except Exception as e:
        print(f"Migration failed: {e}")
        raise


if __name__ == "__main__":
    asyncio.run(runMigration())
