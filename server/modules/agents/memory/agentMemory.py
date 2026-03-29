from __future__ import annotations

import json
import os
import uuid
from typing import Any, Dict, List, Optional

from qdrant_client import AsyncQdrantClient
from qdrant_client.models import Distance, PointStruct, VectorParams

from config.database import db
from config.logger import logger

_QDRANT_URL = os.getenv("QDRANT_URL", "http://localhost:6333")
_VECTOR_DIM = int(os.getenv("AGENT_EMBEDDING_DIM", "1536"))


class AgentMemory:
    """Manages episodic, semantic, and procedural long-term memory for agents."""

    def __init__(self):
        self._client: Optional[AsyncQdrantClient] = None

    def _getClient(self) -> AsyncQdrantClient:
        if self._client is None:
            self._client = AsyncQdrantClient(url=_QDRANT_URL)
        return self._client

    async def _ensureCollection(self, collectionName: str) -> None:
        try:
            client = self._getClient()
            existing = await client.get_collections()
            names = [c.name for c in existing.collections]
            if collectionName not in names:
                await client.create_collection(
                    collection_name=collectionName,
                    vectors_config=VectorParams(size=_VECTOR_DIM, distance=Distance.COSINE),
                )
        except Exception as e:
            logger.error(f"AgentMemory._ensureCollection failed collection={collectionName}: {e}")

    async def _embed(self, text: str) -> List[float]:
        """Produce embedding vector using LightRAG embedding when available, zeros fallback."""
        try:
            from modules.rag.lightragProvider import lightragProvider
            instance = await lightragProvider.getInstance("agent_embed")
            embeddings = await instance.embedding_func([text])
            vec = embeddings[0]
            return vec.tolist() if hasattr(vec, "tolist") else list(vec)
        except Exception as e:
            logger.warning(f"AgentMemory._embed primary failed, using zeros fallback: {e}")
            return [0.0] * _VECTOR_DIM

    async def writeEpisodic(
        self,
        agentType: str,
        userId: str,
        taskId: str,
        content: str,
        metadata: Optional[Dict] = None,
    ) -> str:
        """Record an episodic memory (PostgreSQL only — no vector index)."""
        memoryId = str(uuid.uuid4())
        try:
            if db.useDatabase and db.pool:
                async with db.pool.acquire() as conn:
                    await conn.execute(
                        """INSERT INTO "agentMemories"
                           ("id","agentType","userId","taskId","memoryType","content","metadata")
                           VALUES ($1,$2,$3,$4,'episodic',$5,$6)""",
                        memoryId, agentType, userId, taskId, content,
                        json.dumps(metadata or {}),
                    )
        except Exception as e:
            logger.error(f"AgentMemory.writeEpisodic failed agentType={agentType} userId={userId}: {e}")
        return memoryId

    async def writeSemantic(
        self,
        userId: str,
        agentType: str,
        taskId: str,
        content: str,
        metadata: Optional[Dict] = None,
    ) -> str:
        """Store semantic memory in Qdrant + PostgreSQL."""
        memoryId = str(uuid.uuid4())
        collectionName = f"agent_semantic_{userId.replace('-', '_')}"
        try:
            await self._ensureCollection(collectionName)
            vector = await self._embed(content)
            await self._getClient().upsert(
                collection_name=collectionName,
                points=[PointStruct(
                    id=memoryId,
                    vector=vector,
                    payload={"content": content, "agentType": agentType, "taskId": taskId, **(metadata or {})},
                )],
            )
            if db.useDatabase and db.pool:
                async with db.pool.acquire() as conn:
                    await conn.execute(
                        """INSERT INTO "agentMemories"
                           ("id","agentType","userId","taskId","memoryType","content","metadata","vectorId")
                           VALUES ($1,$2,$3,$4,'semantic',$5,$6,$7)""",
                        memoryId, agentType, userId, taskId, content,
                        json.dumps(metadata or {}), memoryId,
                    )
        except Exception as e:
            logger.error(f"AgentMemory.writeSemantic failed userId={userId} agentType={agentType}: {e}")
        return memoryId

    async def writeProcedural(
        self,
        agentType: str,
        userId: str,
        taskId: str,
        content: str,
        metadata: Optional[Dict] = None,
    ) -> str:
        """Store procedural memory in Qdrant + PostgreSQL."""
        memoryId = str(uuid.uuid4())
        collectionName = f"agent_procedural_{agentType}"
        try:
            await self._ensureCollection(collectionName)
            vector = await self._embed(content)
            await self._getClient().upsert(
                collection_name=collectionName,
                points=[PointStruct(
                    id=memoryId,
                    vector=vector,
                    payload={"content": content, "userId": userId, "taskId": taskId, **(metadata or {})},
                )],
            )
            if db.useDatabase and db.pool:
                async with db.pool.acquire() as conn:
                    await conn.execute(
                        """INSERT INTO "agentMemories"
                           ("id","agentType","userId","taskId","memoryType","content","metadata","vectorId")
                           VALUES ($1,$2,$3,$4,'procedural',$5,$6,$7)""",
                        memoryId, agentType, userId, taskId, content,
                        json.dumps(metadata or {}), memoryId,
                    )
        except Exception as e:
            logger.error(f"AgentMemory.writeProcedural failed agentType={agentType} userId={userId}: {e}")
        return memoryId

    async def recallEpisodic(
        self,
        agentType: str,
        userId: str,
        limit: int = 5,
    ) -> List[Dict]:
        """Retrieve recent episodic memories for this agent + user."""
        try:
            if db.useDatabase and db.pool:
                async with db.pool.acquire() as conn:
                    rows = await conn.fetch(
                        """SELECT "id","content","metadata","createdAt"
                           FROM "agentMemories"
                           WHERE "agentType"=$1 AND "userId"=$2 AND "memoryType"='episodic'
                           ORDER BY "createdAt" DESC LIMIT $3""",
                        agentType, userId, limit,
                    )
                    return [dict(r) for r in rows]
        except Exception as e:
            logger.error(f"AgentMemory.recallEpisodic failed agentType={agentType} userId={userId}: {e}")
        return []

    async def recallSemantic(
        self,
        userId: str,
        query: str,
        limit: int = 5,
    ) -> List[Dict]:
        """Retrieve semantically similar memories for this user."""
        collectionName = f"agent_semantic_{userId.replace('-', '_')}"
        try:
            vector = await self._embed(query)
            client = self._getClient()
            existing = await client.get_collections()
            if collectionName not in [c.name for c in existing.collections]:
                return []
            results = await client.search(
                collection_name=collectionName,
                query_vector=vector,
                limit=limit,
            )
            return [{"content": r.payload.get("content", ""), "score": r.score, "metadata": r.payload} for r in results]
        except Exception as e:
            logger.error(f"AgentMemory.recallSemantic failed userId={userId}: {e}")
        return []

    async def recallProcedural(
        self,
        agentType: str,
        query: str,
        limit: int = 3,
    ) -> List[Dict]:
        """Retrieve procedural patterns for this agent type."""
        collectionName = f"agent_procedural_{agentType}"
        try:
            vector = await self._embed(query)
            client = self._getClient()
            existing = await client.get_collections()
            if collectionName not in [c.name for c in existing.collections]:
                return []
            results = await client.search(
                collection_name=collectionName,
                query_vector=vector,
                limit=limit,
            )
            return [{"content": r.payload.get("content", ""), "score": r.score, "metadata": r.payload} for r in results]
        except Exception as e:
            logger.error(f"AgentMemory.recallProcedural failed agentType={agentType}: {e}")
        return []

    async def deleteMemory(self, memoryId: str, userId: str) -> bool:
        """Delete a memory entry from PostgreSQL (and Qdrant if vectorId exists)."""
        try:
            if db.useDatabase and db.pool:
                async with db.pool.acquire() as conn:
                    row = await conn.fetchrow(
                        """SELECT "memoryType","agentType","vectorId" FROM "agentMemories"
                           WHERE "id"=$1 AND "userId"=$2""",
                        memoryId, userId,
                    )
                    if not row:
                        return False
                    if row["vectorId"] and row["memoryType"] in ("semantic", "procedural"):
                        try:
                            agentType = row["agentType"]
                            collectionName = (
                                f"agent_semantic_{userId.replace('-', '_')}"
                                if row["memoryType"] == "semantic"
                                else f"agent_procedural_{agentType}"
                            )
                            await self._getClient().delete(
                                collection_name=collectionName,
                                points_selector=[row["vectorId"]],
                            )
                        except Exception as qdrantErr:
                            logger.warning(f"AgentMemory.deleteMemory Qdrant delete failed: {qdrantErr}")
                    await conn.execute('DELETE FROM "agentMemories" WHERE "id"=$1', memoryId)
                    return True
        except Exception as e:
            logger.error(f"AgentMemory.deleteMemory failed memoryId={memoryId}: {e}")
        return False


agentMemory = AgentMemory()
