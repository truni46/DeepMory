"""One-time script: backfill doc_index for all existing documents that have a summary."""
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv
load_dotenv(dotenv_path=str(Path(__file__).parent.parent / ".env"))

from config.database import db
from modules.rag.ragService import ragService


async def backfill():
    await db.connect()
    async with db.pool.acquire() as conn:
        rows = await conn.fetch(
            """SELECT id, "userId", filename, summary
               FROM documents
               WHERE summary IS NOT NULL AND summary != ''
               ORDER BY "createdAt" ASC"""
        )
    print(f"Found {len(rows)} documents with summaries to backfill")
    for row in rows:
        try:
            await ragService.upsertDocumentIndex(
                userId=str(row["userId"]),
                documentId=str(row["id"]),
                filename=row["filename"],
                summary=row["summary"],
            )
            print(f"  OK: {row['filename']} ({row['id']})")
        except Exception as e:
            print(f"  FAIL: {row['filename']} ({row['id']}): {e}")
    await db.disconnect()
    print("Backfill complete.")


asyncio.run(backfill())
