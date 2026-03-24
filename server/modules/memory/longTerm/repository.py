"""
Long-term memory repository — PostgreSQL memories table CRUD.
No vector operations here; those are delegated to rag/ragService.
"""
from __future__ import annotations

import json
import uuid
from datetime import datetime
from typing import Dict, List, Optional

from config.database import db


class MemoryRepository:

    async def create(
        self,
        userId: str,
        content: str,
        metadata: Optional[Dict] = None,
    ) -> Dict:
        memoryId = str(uuid.uuid4())
        now = datetime.now()
        record = {
            "id": memoryId,
            "userId": userId,
            "content": content,
            "context": metadata or {},
            "createdAt": now.isoformat(),
        }

        if db.useDatabase and db.pool:
            async with db.pool.acquire() as conn:
                row = await conn.fetchrow(
                    """INSERT INTO memories (id, "userId", content, context, "createdAt")
                       VALUES ($1, $2, $3, $4, $5)
                       RETURNING *""",
                    memoryId, userId, content, json.dumps(metadata or {}), now,
                )
                return dict(row)
        else:
            data = db.read_json("memories")
            data[memoryId] = record
            db.write_json("memories", data)
            return record

    async def getByUser(self, userId: str, limit: int = 50) -> List[Dict]:
        if db.useDatabase and db.pool:
            async with db.pool.acquire() as conn:
                rows = await conn.fetch(
                    """SELECT * FROM memories WHERE "userId" = $1 ORDER BY "createdAt" DESC LIMIT $2""",
                    userId, limit,
                )
                return [dict(r) for r in rows]
        else:
            data = db.read_json("memories")
            memories = [m for m in data.values() if str(m.get("userId")) == str(userId)]
            memories.sort(key=lambda x: x.get("createdAt", ""), reverse=True)
            return memories[:limit]

    async def getById(self, memoryId: str) -> Optional[Dict]:
        if db.useDatabase and db.pool:
            async with db.pool.acquire() as conn:
                row = await conn.fetchrow("SELECT * FROM memories WHERE id = $1", memoryId)
                return dict(row) if row else None
        else:
            data = db.read_json("memories")
            return data.get(memoryId)

    async def delete(self, memoryId: str, userId: str) -> bool:
        if db.useDatabase and db.pool:
            async with db.pool.acquire() as conn:
                result = await conn.execute(
                    """DELETE FROM memories WHERE id = $1 AND "userId" = $2""",
                    memoryId, userId,
                )
                return result == "DELETE 1"
        else:
            data = db.read_json("memories")
            mem = data.get(memoryId)
            if mem and str(mem.get("userId")) == str(userId):
                del data[memoryId]
                db.write_json("memories", data)
                return True
            return False


memoryRepository = MemoryRepository()
