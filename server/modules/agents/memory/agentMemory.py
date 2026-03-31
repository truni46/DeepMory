from __future__ import annotations

import asyncio
import json
import os
import uuid
from typing import Any, Dict, List, Optional

import cohere
from qdrant_client import AsyncQdrantClient
from qdrant_client.models import Distance, PointStruct, VectorParams

from config.database import db
from config.logger import logger
from common.cacheService import cacheService
from modules.llm.embeddingProvider import embeddingService
from modules.llm.llmProvider import llmProvider

_QDRANT_URL = os.getenv("QDRANT_URL", "http://localhost:6333")
_VECTOR_DIM = embeddingService.dimension
_COHERE_API_KEY = os.getenv("COHERE_API_KEY")


class AgentMemory:
    """Manages episodic, semantic, and procedural long-term memory for agents."""

    def __init__(self):
        self._client: Optional[AsyncQdrantClient] = None
        self._cohereClient = cohere.AsyncClient(_COHERE_API_KEY) if _COHERE_API_KEY else None

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
        try:
            return await embeddingService.embed(text)
        except Exception as e:
            logger.warning(f"AgentMemory._embed failed, using zeros fallback: {e}")
            return [0.0] * _VECTOR_DIM

    async def _logHistory(self, memoryId: str, oldMemory: Optional[str], newMemory: Optional[str], event: str) -> None:
        """Audits memory changes (ADD, UPDATE, DELETE)."""
        try:
            if db.useDatabase and db.pool:
                async with db.pool.acquire() as conn:
                    await conn.execute(
                        """INSERT INTO "agentMemoryHistory" 
                           ("memoryId", "oldMemory", "newMemory", "event") 
                           VALUES ($1, $2, $3, $4)""",
                        memoryId, oldMemory, newMemory, event
                    )
        except Exception as e:
            logger.error(f"AgentMemory._logHistory failed memoryId={memoryId}: {e}")


    def addMemory(self, messages: List[Dict], userId: str, agentId: str) -> None:
        """Async fire-and-forget memory ingestion."""
        asyncio.create_task(self._processMemory(messages, userId, agentId))

    async def _processMemory(self, messages: List[Dict], userId: str, agentId: str) -> None:
        """Phase 1: Extract, Phase 2: Dedup, Phase 3: Execute"""
        try:
            # Phase 1: Fact Extraction
            facts = await self._extractFacts(messages)
            if not facts:
                return  # Nothing to remember

            collectionName = f"agent_semantic_{userId.replace('-', '_')}"
            await self._ensureCollection(collectionName)

            for fact in facts:
                # Retrieve similar existing memories for dedup decision
                existingMemories = await self.searchMemory(userId=userId, query=fact, limit=5, threshold=0.6, useRerank=False)
                
                # Phase 2: Dedup / Update Decision
                decision = await self._dedupDecision(fact, existingMemories)
                action = decision.get("action", "ADD").upper()
                memoryId = decision.get("memoryId")
                finalContent = decision.get("content", fact)

                # Phase 3: Execute
                if action == "ADD" or (action == "UPDATE" and not memoryId):
                    # Write new semantic memory
                    newId = await self.writeSemantic(userId, agentId, "mem0_task", finalContent)
                    await self._logHistory(newId, oldMemory=None, newMemory=finalContent, event="ADD")

                elif action == "UPDATE" and memoryId:
                    # Overwrite existing memory
                    oldMemObj = next((m for m in existingMemories if m.get("id") == memoryId), None)
                    oldContent = oldMemObj["content"] if oldMemObj else ""
                    await self.directUpdateMemory(memoryId, finalContent, userId, agentId)
                    await self._logHistory(memoryId, oldMemory=oldContent, newMemory=finalContent, event="UPDATE")

                elif action == "DELETE" and memoryId:
                    # Remove memory
                    oldMemObj = next((m for m in existingMemories if m.get("id") == memoryId), None)
                    oldContent = oldMemObj["content"] if oldMemObj else ""
                    success = await self.deleteMemory(memoryId, userId)
                    if success:
                        await self._logHistory(memoryId, oldMemory=oldContent, newMemory=None, event="DELETE")

        except Exception as e:
            logger.error(f"AgentMemory._processMemory failed userId={userId}: {e}")

    async def _extractFacts(self, messages: List[Dict]) -> List[str]:
        prompt = """You are an expert fact extractor. Extract ONLY factual information from the user messages below. 
Focus strictly on these categories: preferences, personal details, plans, activities, health, professional, misc.
If there are no facts worth remembering (e.g., greetings, generic statements, vague comments), DO NOT extract anything.
Respond in pure JSON format: {"facts": ["fact 1", "fact 2", ...]} or {"facts": []} if nothing is found."""
        
        systemMsg = [{"role": "system", "content": prompt}]
        # Filter out to only human/ai messages if needed, here just pass the block
        allMsgs = systemMsg + messages
        try:
            resp = await llmProvider.generateResponse(allMsgs, stream=False)
            content = resp.content if hasattr(resp, "content") else str(resp)
            
            # Clean possible markdown JSON ticks
            content = content.replace("```json", "").replace("```", "").strip()
            data = json.loads(content)
            
            if isinstance(data, dict):
                return data.get("facts", [])
            elif isinstance(data, list):
                return data
            return []
        except Exception as e:
            logger.error(f"AgentMemory._extractFacts LLM failure: {e}")
            return []

    async def _dedupDecision(self, newFact: str, existingMemories: List[Dict]) -> Dict:
        if not existingMemories:
            return {"action": "ADD", "content": newFact}

        memoriesStr = json.dumps([{"id": m.get("id", m.get("metadata", {}).get("id")), "content": m["content"]} for m in existingMemories], indent=2)
        prompt = f"""You are coordinating memory deduplication.
New Fact: "{newFact}"
Existing Memories:
{memoriesStr}

Rules:
- ADD: The fact is completely new and distinct from existing ones.
- UPDATE: The fact overlaps heavily with an existing memory but contains new details. Provide the 'memoryId' to update, and the merged 'content'.
- DELETE: The new fact completely contradicts an existing memory without replacing it cleanly, or the user explicitly asked to forget it. Provide 'memoryId'.
- NONE: The exact same factual information is already present.

Response must be pure JSON: {{"action": "ADD|UPDATE|DELETE|NONE", "memoryId": "<string or null>", "content": "<merged content if UPDATE>"}}"""
        
        try:
            resp = await llmProvider.generateResponse([{"role": "user", "content": prompt}], stream=False)
            content = resp.content if hasattr(resp, "content") else str(resp)
            content = content.replace("```json", "").replace("```", "").strip()
            return json.loads(content)
        except Exception as e:
            logger.error(f"AgentMemory._dedupDecision LLM failure: {e}")
            return {"action": "ADD", "content": newFact}

    async def searchMemory(self, userId: str, query: str, limit: int = 5, topK: int = 50, threshold: float = 0.5, useRerank: bool = True) -> List[Dict]:
        """Search workflow: Vector Search -> Filter -> Rerank (Cohere)"""
        try:
            memories = await self.recallSemantic(userId, query, limit=topK)
            filtered = [m for m in memories if m.get("score", 0) >= threshold]
            
            if not filtered:
                return []
            
            if useRerank and self._cohereClient:
                try:
                    docs = [m["content"] for m in filtered]
                    reranked = await self._cohereClient.rerank(
                        query=query, documents=docs, model='rerank-english-v3.0', top_n=limit
                    )
                    return [filtered[r.index] for r in reranked.results]
                except Exception as rankErr:
                    logger.warning(f"Cohere rerank failed: {rankErr}")
                    return filtered[:limit]
            else:
                return filtered[:limit]
        except Exception as e:
            logger.error(f"AgentMemory.searchMemory failed: {e}")
            return []

    async def getHistory(self, memoryId: str) -> List[Dict]:
        """Audit trail for a specific memory."""
        try:
            if db.useDatabase and db.pool:
                async with db.pool.acquire() as conn:
                    rows = await conn.fetch(
                        """SELECT "id","oldMemory","newMemory","event","createdAt" 
                           FROM "agentMemoryHistory" 
                           WHERE "memoryId"=$1 ORDER BY "createdAt" ASC""",
                        memoryId
                    )
                    return [dict(r) for r in rows]
        except Exception as e:
            logger.error(f"AgentMemory.getHistory failed memoryId={memoryId}: {e}")
        return []

    async def directUpdateMemory(self, memoryId: str, content: str, userId: str, agentType: str) -> bool:
        """Directly overwrite a memory without Phase 1/2 LLM extraction."""
        collectionName = f"agent_semantic_{userId.replace('-', '_')}"
        try:
            vector = await self._embed(content)
            # Update Qdrant
            await self._getClient().upsert(
                collection_name=collectionName,
                points=[PointStruct(
                    id=memoryId,
                    vector=vector,
                    payload={"content": content, "agentType": agentType, "userId": userId}
                )]
            )
            # Update Postgres
            if db.useDatabase and db.pool:
                async with db.pool.acquire() as conn:
                    await conn.execute(
                        """UPDATE "agentMemories" SET "content"=$1 WHERE "id"=$2 AND "userId"=$3""",
                        content, memoryId, userId
                    )
            return True
        except Exception as e:
            logger.error(f"AgentMemory.directUpdateMemory failed memoryId={memoryId}: {e}")
            return False

    async def writeEpisodic(
        self,
        agentType: str,
        userId: str,
        taskId: str,
        content: str,
        metadata: Optional[Dict] = None,
    ) -> str:
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
            return [{"id": r.id, "content": r.payload.get("content", ""), "score": r.score, "metadata": r.payload} for r in results]
        except Exception as e:
            logger.error(f"AgentMemory.recallSemantic failed userId={userId}: {e}")
        return []

    async def recallProcedural(
        self,
        agentType: str,
        query: str,
        limit: int = 3,
    ) -> List[Dict]:
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
            return [{"id": r.id, "content": r.payload.get("content", ""), "score": r.score, "metadata": r.payload} for r in results]
        except Exception as e:
            logger.error(f"AgentMemory.recallProcedural failed agentType={agentType}: {e}")
        return []

    async def deleteMemory(self, memoryId: str, userId: str) -> bool:
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


    async def addShortTermMemory(self, conversationId: str, messages: List[Dict], expire: int = 24 * 3600) -> None:
        """Cache conversation context for short term usage with TTL."""
        try:
            key = f"agent:conversation:{conversationId}:memory"
            await cacheService.set(key, messages, expire=expire)
        except Exception as e:
            logger.error(f"AgentMemory.addShortTermMemory failed conversationId={conversationId}: {e}")

    async def getShortTermMemory(self, conversationId: str) -> List[Dict]:
        """Retrieve recent conversation context."""
        try:
            key = f"agent:conversation:{conversationId}:memory"
            return await cacheService.get(key) or []
        except Exception as e:
            logger.error(f"AgentMemory.getShortTermMemory failed conversationId={conversationId}: {e}")
            return []

agentMemory = AgentMemory()
