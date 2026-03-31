# Multi-Agent System Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a LangGraph-based multi-agent system with Supervisor pattern, hybrid memory (Redis short-term + PostgreSQL/Qdrant long-term), and 6 specialized agents integrated into the existing FastAPI backend.

**Architecture:** LangGraph Supervisor Pattern with 6 agents (Research, Planner, Implement, Testing, BrowserAgent, Report). Shared TaskState flows through Redis checkpointer. Long-term memory uses 3 types: episodic (PostgreSQL), semantic (Qdrant), procedural (Qdrant).

**Tech Stack:** LangGraph, LangChain, Tavily Search, Claude in Chrome MCP (BrowserAgent), asyncpg, Redis, Qdrant

---

## Task 1: Install Dependencies

**Files touched:** `server/.venv` (virtual environment), `server/requirements.txt` (update)

- [ ] Activate the existing virtual environment:
  ```bash
  cd server
  .venv\Scripts\activate   # Windows
  # or: source .venv/bin/activate  # Linux/Mac
  ```
- [ ] Install LangGraph and LangChain core packages:
  ```bash
  pip install langgraph langchain langchain-core langchain-community
  ```
- [ ] Install Tavily search client:
  ```bash
  pip install tavily-python
  ```
- [ ] Install Qdrant client (for direct agent memory collections, separate from LightRAG):
  ```bash
  pip install qdrant-client
  ```
- [ ] Verify installations resolve without conflict against existing packages (`lightrag`, `httpx`, `fastapi`):
  ```bash
  pip check
  ```
- [ ] Update `server/requirements.txt` to include the new packages with pinned versions from `pip freeze`.
- [ ] Commit:
  ```
  git add server/requirements.txt
  git commit -m "feat: add LangGraph, LangChain, Tavily, Qdrant client dependencies"
  ```

---

## Task 2: Database Migration

**Files to create:** `server/migrations/003_agent_system.sql`
**Files to modify:** `server/migrations/migrate.py`

### 2.1 Create migration SQL

Create `server/migrations/003_agent_system.sql` with the following content:

```sql
-- Migration 003: agent system tables

CREATE TABLE IF NOT EXISTS "agentTasks" (
    "id"             UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    "userId"         UUID NOT NULL REFERENCES users("id") ON DELETE CASCADE,
    "conversationId" UUID REFERENCES conversations("id") ON DELETE SET NULL,
    "projectId"      UUID REFERENCES projects("id") ON DELETE SET NULL,
    "goal"           TEXT NOT NULL,
    "status"         VARCHAR(32) NOT NULL DEFAULT 'running'
                         CHECK ("status" IN ('running','completed','failed','partial_failure','cancelled')),
    "errorMessage"   TEXT,
    "finalReport"    TEXT,
    "createdAt"      TIMESTAMPTZ DEFAULT now(),
    "updatedAt"      TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE IF NOT EXISTS "agentRuns" (
    "id"           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    "taskId"       UUID NOT NULL REFERENCES "agentTasks"("id") ON DELETE CASCADE,
    "agentType"    VARCHAR(64) NOT NULL,
    "iterationNum" INTEGER NOT NULL,
    "input"        JSONB,
    "output"       JSONB,
    "status"       VARCHAR(32) NOT NULL,
    "durationMs"   INTEGER,
    "createdAt"    TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE IF NOT EXISTS "agentMemories" (
    "id"         UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    "agentType"  VARCHAR(64) NOT NULL,
    "userId"     UUID NOT NULL REFERENCES users("id") ON DELETE CASCADE,
    "taskId"     UUID REFERENCES "agentTasks"("id") ON DELETE SET NULL,
    "memoryType" VARCHAR(16) NOT NULL
                     CHECK ("memoryType" IN ('episodic','semantic','procedural')),
    "content"    TEXT NOT NULL,
    "metadata"   JSONB DEFAULT '{}',
    "vectorId"   VARCHAR(128),
    "createdAt"  TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_agent_tasks_user   ON "agentTasks"("userId");
CREATE INDEX IF NOT EXISTS idx_agent_tasks_status ON "agentTasks"("status");
CREATE INDEX IF NOT EXISTS idx_agent_runs_task    ON "agentRuns"("taskId");
CREATE INDEX IF NOT EXISTS idx_agent_memories_user_type
    ON "agentMemories"("userId", "agentType", "memoryType");

CREATE OR REPLACE FUNCTION update_agent_tasks_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW."updatedAt" = now();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_agent_tasks_updated_at ON "agentTasks";
CREATE TRIGGER trg_agent_tasks_updated_at
    BEFORE UPDATE ON "agentTasks"
    FOR EACH ROW EXECUTE FUNCTION update_agent_tasks_updated_at();
```

### 2.2 Update migrate.py to run all numbered migrations

Update `server/migrations/migrate.py` to discover and run all `00N_*.sql` files in order rather than hard-coding `001_initial_schema.sql`. Pattern:

```python
import asyncio
import asyncpg
import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

async def runMigration():
    """Run all pending database migrations in numeric order."""
    print("Running database migrations...")
    dbConfig = {
        'host': os.getenv('DB_HOST', 'localhost'),
        'port': int(os.getenv('DB_PORT', 5432)),
        'database': os.getenv('DB_NAME', 'deepmory_db'),
        'user': os.getenv('DB_USER', 'deepmory'),
        'password': os.getenv('DB_PASSWORD', ''),
    }
    try:
        conn = await asyncpg.connect(**dbConfig)
        print(f"Connected to database: {dbConfig['database']}")

        migrationDir = Path(__file__).parent
        sqlFiles = sorted(migrationDir.glob('[0-9][0-9][0-9]_*.sql'))

        for sqlFile in sqlFiles:
            print(f"Running: {sqlFile.name}")
            sql = sqlFile.read_text(encoding='utf-8')
            try:
                await conn.execute(sql)
                print(f"  OK: {sqlFile.name}")
            except Exception as e:
                print(f"  WARN: {sqlFile.name} â€” {e} (may already exist, continuing)")

        await conn.close()
        print("Migrations completed.")
    except Exception as e:
        print(f"Migration failed: {e}")
        raise

if __name__ == "__main__":
    asyncio.run(runMigration())
```

### 2.3 Run migration

```bash
cd server
.venv\Scripts\activate
python migrations/migrate.py
```

Verify tables exist:
```bash
# Using psql or any DB client:
# SELECT table_name FROM information_schema.tables WHERE table_name IN ('agentTasks','agentRuns','agentMemories');
```

- [ ] Create `server/migrations/003_agent_system.sql`
- [ ] Update `server/migrations/migrate.py` to multi-file runner
- [ ] Run `python migrations/migrate.py` and confirm no errors
- [ ] Commit:
  ```
  git add server/migrations/003_agent_system.sql server/migrations/migrate.py
  git commit -m "feat: add agent system database tables (agentTasks, agentRuns, agentMemories)"
  ```

---

## Task 3: DeepMoryLLM Adapter

**File to create:** `server/modules/agents/deepMoryLLM.py`

This adapter wraps the existing `llmProvider` singleton into a LangChain `BaseChatModel`. It is a single-file adapter â€” not a provider registry. No additional provider files should be created alongside it.

Key design decisions from the spec and codebase analysis:
- `_agenerate()` calls `llmProvider.generateResponse(messages, stream=False)` and wraps the string result in `ChatResult`.
- `_astream()` calls `llmProvider.streamResponse(messages)` (the async generator) and yields `ChatGenerationChunk` per text chunk.
- `GeminiNativeProvider` returns a generator from `generateResponse(stream=True)` but for providers that lack native tool-call support, the Supervisor must use `_agenerate()` only.
- The adapter converts LangChain `BaseMessage` objects to the `List[Dict]` format that `llmProvider` expects (`{"role": ..., "content": ...}`).

```python
from __future__ import annotations

import os
from typing import Any, AsyncGenerator, Iterator, List, Optional

from langchain_core.callbacks import AsyncCallbackManagerForLLMRun, CallbackManagerForLLMRun
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage, BaseMessage
from langchain_core.outputs import ChatGeneration, ChatGenerationChunk, ChatResult

from config.logger import logger
from modules.llm.llmProvider import llmProvider


def _toDict(message: BaseMessage) -> dict:
    """Convert a LangChain BaseMessage to the role/content dict llmProvider expects."""
    roleMap = {"human": "user", "ai": "assistant", "system": "system", "tool": "tool"}
    role = roleMap.get(message.type, message.type)
    return {"role": role, "content": message.content}


class DeepMoryLLM(BaseChatModel):
    """LangChain BaseChatModel adapter wrapping the existing llmProvider singleton."""

    @property
    def _llm_type(self) -> str:
        return "deepmory"

    def _generate(
        self,
        messages: List[BaseMessage],
        stop: Optional[List[str]] = None,
        run_manager: Optional[CallbackManagerForLLMRun] = None,
        **kwargs: Any,
    ) -> ChatResult:
        raise NotImplementedError("Use _agenerate for async operation.")

    async def _agenerate(
        self,
        messages: List[BaseMessage],
        stop: Optional[List[str]] = None,
        run_manager: Optional[AsyncCallbackManagerForLLMRun] = None,
        **kwargs: Any,
    ) -> ChatResult:
        """Non-streaming generation â€” used by the Supervisor node."""
        try:
            dicts = [_toDict(m) for m in messages]
            text = await llmProvider.generateResponse(dicts, stream=False)
            if not isinstance(text, str):
                # Fallback: drain the generator if provider returned one
                chunks = []
                async for chunk in text:
                    chunks.append(chunk)
                text = "".join(chunks)
            return ChatResult(generations=[ChatGeneration(message=AIMessage(content=text))])
        except Exception as e:
            logger.error(f"DeepMoryLLM._agenerate failed: {e}")
            raise

    async def _astream(
        self,
        messages: List[BaseMessage],
        stop: Optional[List[str]] = None,
        run_manager: Optional[AsyncCallbackManagerForLLMRun] = None,
        **kwargs: Any,
    ) -> AsyncGenerator[ChatGenerationChunk, None]:
        """Streaming generation â€” used by sub-agent nodes."""
        try:
            dicts = [_toDict(m) for m in messages]
            async for chunk in llmProvider.streamResponse(dicts):
                yield ChatGenerationChunk(message=AIMessage(content=chunk))
        except Exception as e:
            logger.error(f"DeepMoryLLM._astream failed: {e}")
            raise


deepMoryLLM = DeepMoryLLM()
```

- [ ] Create `server/modules/agents/` directory (and `__init__.py`)
- [ ] Create `server/modules/agents/deepMoryLLM.py` with the code above
- [ ] Manually test import: `python -c "from modules.agents.deepMoryLLM import deepMoryLLM; print(deepMoryLLM._llm_type)"`
- [ ] Commit:
  ```
  git add server/modules/agents/
  git commit -m "feat: add DeepMoryLLM adapter wrapping llmProvider as LangChain BaseChatModel"
  ```

---

## Task 4: TaskState Schema

**File to create:** `server/modules/agents/orchestrator/taskState.py`

```python
from __future__ import annotations

import os
from typing import Literal, Optional
from typing_extensions import TypedDict

from langchain_core.messages import BaseMessage


class TaskState(TypedDict):
    # Identity
    taskId: str
    userId: str
    conversationId: Optional[str]
    projectId: Optional[str]

    # Flow control
    currentAgent: str
    nextAgent: Optional[str]
    iterationCount: int
    maxIterations: int
    status: Literal["running", "completed", "failed", "partial_failure", "cancelled"]
    errorMessage: Optional[str]

    # Conversation memory (short-term) â€” LangGraph manages this via Annotated reducer
    messages: list[BaseMessage]

    # Agent outputs (accumulated)
    goal: str
    researchFindings: list[dict]
    plan: Optional[dict]
    implementationResult: Optional[dict]
    testingResult: Optional[dict]
    finalReport: Optional[str]


def buildInitialState(
    taskId: str,
    userId: str,
    goal: str,
    conversationId: Optional[str] = None,
    projectId: Optional[str] = None,
) -> TaskState:
    """Construct the initial TaskState for a new task run."""
    return TaskState(
        taskId=taskId,
        userId=userId,
        conversationId=conversationId,
        projectId=projectId,
        currentAgent="supervisor",
        nextAgent=None,
        iterationCount=0,
        maxIterations=int(os.getenv("AGENT_MAX_ITERATIONS", "10")),
        status="running",
        errorMessage=None,
        messages=[],
        goal=goal,
        researchFindings=[],
        plan=None,
        implementationResult=None,
        testingResult=None,
        finalReport=None,
    )
```

Important: LangGraph requires `messages` to use `Annotated[list[BaseMessage], add_messages]` in the actual graph state definition so message lists are appended rather than replaced. In `graphBuilder.py` (Task 8), the StateGraph will be typed with an `Annotated` variant. `TaskState` here serves as the documentation-accurate TypedDict for the plan and for repository serialization.

- [ ] Create `server/modules/agents/orchestrator/` directory (and `__init__.py`)
- [ ] Create `server/modules/agents/orchestrator/taskState.py`
- [ ] Commit:
  ```
  git add server/modules/agents/orchestrator/
  git commit -m "feat: add TaskState TypedDict schema for agent graph shared state"
  ```

---

## Task 5: Memory Layer

**Files to create:**
- `server/modules/agents/memory/taskMemory.py` â€” RedisCheckpointer
- `server/modules/agents/memory/agentMemory.py` â€” episodic / semantic / procedural

### 5.1 taskMemory.py â€” RedisCheckpointer

The checkpointer implements LangGraph's `BaseCheckpointSaver` (`aget`, `aput`, `alist`). It uses the existing `cacheService` Redis connection.

```python
from __future__ import annotations

import json
import os
from typing import Any, AsyncIterator, Optional

from langchain_core.runnables import RunnableConfig
from langgraph.checkpoint.base import BaseCheckpointSaver, Checkpoint, CheckpointMetadata

from common.cacheService import cacheService
from config.logger import logger

_CHECKPOINT_TTL = int(os.getenv("AGENT_CHECKPOINT_TTL", str(24 * 3600)))


class RedisCheckpointer(BaseCheckpointSaver):
    """LangGraph checkpoint saver backed by the existing Redis (cacheService)."""

    @staticmethod
    def _latestKey(taskId: str) -> str:
        return f"agent:checkpoint:{taskId}:latest"

    @staticmethod
    def _stepKey(taskId: str, stepId: str) -> str:
        return f"agent:checkpoint:{taskId}:{stepId}"

    async def aget(
        self, config: RunnableConfig, **kwargs: Any
    ) -> Optional[Checkpoint]:
        try:
            taskId = config["configurable"].get("thread_id", "unknown")
            key = self._latestKey(taskId)
            data = await cacheService.get(key)
            if data is None:
                return None
            return Checkpoint(**data) if isinstance(data, dict) else None
        except Exception as e:
            logger.error(f"RedisCheckpointer.aget failed taskId={config}: {e}")
            return None

    async def aput(
        self,
        config: RunnableConfig,
        checkpoint: Checkpoint,
        metadata: CheckpointMetadata,
        **kwargs: Any,
    ) -> RunnableConfig:
        try:
            taskId = config["configurable"].get("thread_id", "unknown")
            stepId = str(checkpoint.get("id", "step"))
            payload = dict(checkpoint)
            await cacheService.set(self._latestKey(taskId), payload, expire=_CHECKPOINT_TTL)
            await cacheService.set(self._stepKey(taskId, stepId), payload, expire=_CHECKPOINT_TTL)
            return config
        except Exception as e:
            logger.error(f"RedisCheckpointer.aput failed taskId={config}: {e}")
            return config

    async def alist(
        self, config: RunnableConfig, **kwargs: Any
    ) -> AsyncIterator[Checkpoint]:
        # Phase 1: yield only the latest checkpoint
        try:
            taskId = config["configurable"].get("thread_id", "unknown")
            key = self._latestKey(taskId)
            data = await cacheService.get(key)
            if data:
                yield Checkpoint(**data)
        except Exception as e:
            logger.error(f"RedisCheckpointer.alist failed taskId={config}: {e}")

    async def writeMessages(self, taskId: str, messages: list) -> None:
        """Convenience: write full message list to the agent:task key for sub-agents to read."""
        try:
            key = f"agent:task:{taskId}:messages"
            serialized = [
                {"type": m.__class__.__name__, "content": m.content}
                for m in messages
            ]
            await cacheService.set(key, serialized, expire=_CHECKPOINT_TTL)
        except Exception as e:
            logger.error(f"RedisCheckpointer.writeMessages failed taskId={taskId}: {e}")

    async def readMessages(self, taskId: str) -> list:
        """Read cached message list (convenience read, not authoritative checkpoint)."""
        try:
            key = f"agent:task:{taskId}:messages"
            return await cacheService.get(key) or []
        except Exception as e:
            logger.error(f"RedisCheckpointer.readMessages failed taskId={taskId}: {e}")
            return []


taskMemory = RedisCheckpointer()
```

### 5.2 agentMemory.py â€” Long-term memory (episodic / semantic / procedural)

This file uses `qdrant_client` directly (not through LightRAG) so that agent memory collections are fully decoupled from the RAG pipeline.

```python
from __future__ import annotations

import os
import uuid
from typing import Any, Dict, List, Optional

from qdrant_client import AsyncQdrantClient
from qdrant_client.models import Distance, PointStruct, VectorParams, Filter, FieldCondition, MatchValue

from config.database import db
from config.logger import logger

_QDRANT_URL = os.getenv("QDRANT_URL", "http://localhost:6333")
_VECTOR_DIM = int(os.getenv("AGENT_EMBEDDING_DIM", "1536"))


class AgentMemory:

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
        """Produce embedding vector. Uses the same embedding approach as ragService where possible."""
        try:
            from modules.rag.lightragProvider import lightragProvider
            instance = await lightragProvider.getInstance("agent_embed")
            embeddings = await instance.embedding_func([text])
            return embeddings[0].tolist() if hasattr(embeddings[0], "tolist") else list(embeddings[0])
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
        """Record an episodic memory entry (PostgreSQL only)."""
        memoryId = str(uuid.uuid4())
        try:
            if db.useDatabase and db.pool:
                async with db.pool.acquire() as conn:
                    await conn.execute(
                        """INSERT INTO "agentMemories"
                           ("id","agentType","userId","taskId","memoryType","content","metadata")
                           VALUES ($1,$2,$3,$4,'episodic',$5,$6)""",
                        memoryId, agentType, userId, taskId, content,
                        __import__("json").dumps(metadata or {}),
                    )
            return memoryId
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
        """Store a semantic memory in Qdrant + PostgreSQL."""
        memoryId = str(uuid.uuid4())
        collectionName = f"agent_semantic_{userId}"
        try:
            await self._ensureCollection(collectionName)
            vector = await self._embed(content)
            client = self._getClient()
            await client.upsert(
                collection_name=collectionName,
                points=[PointStruct(id=memoryId, vector=vector, payload={"content": content, "agentType": agentType, "taskId": taskId, **(metadata or {})})],
            )
            if db.useDatabase and db.pool:
                async with db.pool.acquire() as conn:
                    await conn.execute(
                        """INSERT INTO "agentMemories"
                           ("id","agentType","userId","taskId","memoryType","content","metadata","vectorId")
                           VALUES ($1,$2,$3,$4,'semantic',$5,$6,$7)""",
                        memoryId, agentType, userId, taskId, content,
                        __import__("json").dumps(metadata or {}), memoryId,
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
        """Store a procedural memory in Qdrant + PostgreSQL."""
        memoryId = str(uuid.uuid4())
        collectionName = f"agent_procedural_{agentType}"
        try:
            await self._ensureCollection(collectionName)
            vector = await self._embed(content)
            client = self._getClient()
            await client.upsert(
                collection_name=collectionName,
                points=[PointStruct(id=memoryId, vector=vector, payload={"content": content, "userId": userId, "taskId": taskId, **(metadata or {})})],
            )
            if db.useDatabase and db.pool:
                async with db.pool.acquire() as conn:
                    await conn.execute(
                        """INSERT INTO "agentMemories"
                           ("id","agentType","userId","taskId","memoryType","content","metadata","vectorId")
                           VALUES ($1,$2,$3,$4,'procedural',$5,$6,$7)""",
                        memoryId, agentType, userId, taskId, content,
                        __import__("json").dumps(metadata or {}), memoryId,
                    )
        except Exception as e:
            logger.error(f"AgentMemory.writeProcedural failed agentType={agentType} userId={userId}: {e}")
        return memoryId

    async def recallEpisodic(
        self, agentType: str, userId: str, limit: int = 5
    ) -> List[Dict]:
        """Fetch recent episodic memories for agentType + userId from PostgreSQL."""
        try:
            if db.useDatabase and db.pool:
                async with db.pool.acquire() as conn:
                    rows = await conn.fetch(
                        """SELECT "id","content","metadata","taskId","createdAt"
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
        self, userId: str, query: str, limit: int = 5
    ) -> List[Dict]:
        """Vector similarity search in agent_semantic_{userId} Qdrant collection."""
        collectionName = f"agent_semantic_{userId}"
        try:
            await self._ensureCollection(collectionName)
            vector = await self._embed(query)
            client = self._getClient()
            results = await client.search(
                collection_name=collectionName, query_vector=vector, limit=limit
            )
            return [{"content": r.payload.get("content", ""), "score": r.score, "id": r.id} for r in results]
        except Exception as e:
            logger.error(f"AgentMemory.recallSemantic failed userId={userId}: {e}")
        return []

    async def recallProcedural(
        self, agentType: str, query: str, limit: int = 5
    ) -> List[Dict]:
        """Vector similarity search in agent_procedural_{agentType} Qdrant collection."""
        collectionName = f"agent_procedural_{agentType}"
        try:
            await self._ensureCollection(collectionName)
            vector = await self._embed(query)
            client = self._getClient()
            results = await client.search(
                collection_name=collectionName, query_vector=vector, limit=limit
            )
            return [{"content": r.payload.get("content", ""), "score": r.score, "id": r.id} for r in results]
        except Exception as e:
            logger.error(f"AgentMemory.recallProcedural failed agentType={agentType}: {e}")
        return []

    async def deleteMemory(self, memoryId: str) -> bool:
        """Delete a memory from PostgreSQL and (if vector) from Qdrant."""
        try:
            if db.useDatabase and db.pool:
                async with db.pool.acquire() as conn:
                    row = await conn.fetchrow(
                        """SELECT "memoryType","agentType","userId","vectorId"
                           FROM "agentMemories" WHERE "id"=$1""",
                        memoryId,
                    )
                    if not row:
                        return False
                    if row["memoryType"] in ("semantic", "procedural") and row["vectorId"]:
                        collectionName = (
                            f"agent_semantic_{row['userId']}"
                            if row["memoryType"] == "semantic"
                            else f"agent_procedural_{row['agentType']}"
                        )
                        try:
                            client = self._getClient()
                            await client.delete(
                                collection_name=collectionName,
                                points_selector=[row["vectorId"]],
                            )
                        except Exception as qdrantErr:
                            logger.warning(f"AgentMemory Qdrant delete failed memoryId={memoryId}: {qdrantErr}")
                    await conn.execute("""DELETE FROM "agentMemories" WHERE "id"=$1""", memoryId)
                    return True
        except Exception as e:
            logger.error(f"AgentMemory.deleteMemory failed memoryId={memoryId}: {e}")
        return False


agentMemory = AgentMemory()
```

- [ ] Create `server/modules/agents/memory/` directory (and `__init__.py`)
- [ ] Create `server/modules/agents/memory/taskMemory.py`
- [ ] Create `server/modules/agents/memory/agentMemory.py`
- [ ] Commit:
  ```
  git add server/modules/agents/memory/
  git commit -m "feat: add RedisCheckpointer (taskMemory) and episodic/semantic/procedural AgentMemory"
  ```

---

## Task 6: Agent Tools

**File to create:** `server/modules/agents/tools/` directory with one file per agent group

All tools are plain `async` functions decorated with `@tool` from `langchain_core.tools`. They take typed arguments and return strings or dicts. No tool file imports from another tool file.

### 6.1 `server/modules/agents/tools/researchTools.py`

```python
from __future__ import annotations

import os
from langchain_core.tools import tool
from config.logger import logger
from modules.rag.ragService import ragService


@tool
async def webSearch(query: str) -> str:
    """Search the web using Tavily for recent information on a query."""
    try:
        from tavily import AsyncTavilyClient
        apiKey = os.getenv("TAVILY_API_KEY", "")
        client = AsyncTavilyClient(api_key=apiKey)
        response = await client.search(query, max_results=5)
        results = response.get("results", [])
        return "\n\n".join(
            f"[{r.get('title','')}] {r.get('url','')}\n{r.get('content','')}"
            for r in results
        )
    except Exception as e:
        logger.error(f"webSearch failed query={query!r}: {e}")
        return f"webSearch error: {e}"


@tool
async def ragSearch(query: str, projectId: str = "", userId: str = "") -> str:
    """Search internal knowledge base via ragService."""
    try:
        if projectId:
            results = await ragService.searchContext(query, projectId, limit=5)
        else:
            results = await ragService.searchMemoryVectors(userId, query, limit=5)
        return "\n\n".join(r.document.content for r in results) if results else "No results found."
    except Exception as e:
        logger.error(f"ragSearch failed query={query!r} projectId={projectId}: {e}")
        return f"ragSearch error: {e}"


@tool
async def documentReader(filePath: str) -> str:
    """Read and return the contents of a file from the agent workspace."""
    try:
        workspaceDir = os.path.abspath(os.getenv("AGENT_WORKSPACE_DIR", "./agent_workspace"))
        fullPath = os.path.abspath(os.path.join(workspaceDir, filePath))
        if not fullPath.startswith(workspaceDir):
            return "Access denied: path outside workspace."
        with open(fullPath, "r", encoding="utf-8", errors="ignore") as f:
            return f.read()
    except Exception as e:
        logger.error(f"documentReader failed filePath={filePath!r}: {e}")
        return f"documentReader error: {e}"
```

### 6.2 `server/modules/agents/tools/plannerTools.py`

```python
from __future__ import annotations

import json
from langchain_core.tools import tool
from config.logger import logger


@tool
async def createPlan(goal: str, researchSummary: str) -> str:
    """Produce a structured JSON plan from goal + research findings."""
    # The LLM invokes this tool; the tool's job is to format and validate structure.
    # In the Planner agent node the LLM generates the plan content; this tool records it.
    try:
        plan = {
            "goal": goal,
            "researchSummary": researchSummary,
            "steps": [],
            "status": "draft",
        }
        return json.dumps(plan)
    except Exception as e:
        logger.error(f"createPlan failed goal={goal!r}: {e}")
        return json.dumps({"error": str(e)})


@tool
async def validatePlan(planJson: str) -> str:
    """Validate a plan JSON string and return 'valid' or a list of errors."""
    try:
        plan = json.loads(planJson)
        errors = []
        if not plan.get("goal"):
            errors.append("Missing 'goal'")
        if not isinstance(plan.get("steps"), list) or len(plan["steps"]) == 0:
            errors.append("Plan must have at least one step")
        return "valid" if not errors else "invalid: " + "; ".join(errors)
    except Exception as e:
        logger.error(f"validatePlan failed: {e}")
        return f"validatePlan error: {e}"
```

### 6.3 `server/modules/agents/tools/implementTools.py`

```python
from __future__ import annotations

import asyncio
import os
import subprocess
from langchain_core.tools import tool
from config.logger import logger

_WORKSPACE = os.path.abspath(os.getenv("AGENT_WORKSPACE_DIR", "./agent_workspace"))
_SHELL_TIMEOUT = int(os.getenv("AGENT_SHELL_TIMEOUT", "30"))
_ALLOWED_COMMANDS = ("python", "pytest", "npm", "pip")


@tool
async def codeWriter(filename: str, content: str) -> str:
    """Write code content to a file inside the agent workspace."""
    try:
        fullPath = os.path.abspath(os.path.join(_WORKSPACE, filename))
        if not fullPath.startswith(_WORKSPACE):
            return "Access denied: path outside workspace."
        os.makedirs(os.path.dirname(fullPath), exist_ok=True)
        with open(fullPath, "w", encoding="utf-8") as f:
            f.write(content)
        return f"Written: {filename}"
    except Exception as e:
        logger.error(f"codeWriter failed filename={filename!r}: {e}")
        return f"codeWriter error: {e}"


@tool
async def fileWriter(filename: str, content: str) -> str:
    """Write arbitrary text content to a file inside the agent workspace."""
    return await codeWriter.ainvoke({"filename": filename, "content": content})


@tool
async def shellRunner(command: str) -> str:
    """Run an allowlisted shell command inside the agent workspace (sandboxed)."""
    try:
        parts = command.strip().split()
        if not parts or parts[0] not in _ALLOWED_COMMANDS:
            return f"Command not allowed. Permitted: {_ALLOWED_COMMANDS}"
        proc = await asyncio.create_subprocess_exec(
            *parts,
            cwd=_WORKSPACE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env={**os.environ, "PATH": os.environ.get("PATH", "")},
        )
        try:
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=_SHELL_TIMEOUT)
        except asyncio.TimeoutError:
            proc.kill()
            return f"shellRunner timeout after {_SHELL_TIMEOUT}s"
        output = stdout.decode(errors="replace") + stderr.decode(errors="replace")
        return output[:4000]
    except Exception as e:
        logger.error(f"shellRunner failed command={command!r}: {e}")
        return f"shellRunner error: {e}"
```

### 6.4 `server/modules/agents/tools/testingTools.py`

```python
from __future__ import annotations

import asyncio
import os
from langchain_core.tools import tool
from config.logger import logger

_WORKSPACE = os.path.abspath(os.getenv("AGENT_WORKSPACE_DIR", "./agent_workspace"))
_SHELL_TIMEOUT = int(os.getenv("AGENT_SHELL_TIMEOUT", "30"))


@tool
async def codeRunner(filename: str) -> str:
    """Execute a Python file in the workspace and return stdout/stderr."""
    try:
        fullPath = os.path.abspath(os.path.join(_WORKSPACE, filename))
        if not fullPath.startswith(_WORKSPACE):
            return "Access denied."
        proc = await asyncio.create_subprocess_exec(
            "python", fullPath,
            cwd=_WORKSPACE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=_SHELL_TIMEOUT)
        return (stdout.decode(errors="replace") + stderr.decode(errors="replace"))[:4000]
    except asyncio.TimeoutError:
        return f"codeRunner timeout after {_SHELL_TIMEOUT}s"
    except Exception as e:
        logger.error(f"codeRunner failed filename={filename!r}: {e}")
        return f"codeRunner error: {e}"


@tool
async def testRunner(testPath: str = ".") -> str:
    """Run pytest on a path within the workspace and return results."""
    try:
        fullPath = os.path.abspath(os.path.join(_WORKSPACE, testPath))
        if not fullPath.startswith(_WORKSPACE):
            return "Access denied."
        proc = await asyncio.create_subprocess_exec(
            "pytest", fullPath, "--tb=short", "-q",
            cwd=_WORKSPACE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=_SHELL_TIMEOUT)
        return (stdout.decode(errors="replace") + stderr.decode(errors="replace"))[:4000]
    except asyncio.TimeoutError:
        return f"testRunner timeout after {_SHELL_TIMEOUT}s"
    except Exception as e:
        logger.error(f"testRunner failed testPath={testPath!r}: {e}")
        return f"testRunner error: {e}"


@tool
async def validator(content: str, criteria: str) -> str:
    """Validate content against criteria using simple rule checks. Returns 'pass' or failure reasons."""
    try:
        issues = []
        if "non-empty" in criteria.lower() and not content.strip():
            issues.append("Content is empty")
        return "pass" if not issues else "fail: " + "; ".join(issues)
    except Exception as e:
        logger.error(f"validator failed: {e}")
        return f"validator error: {e}"


@tool
async def testCaseGenerator(codeContent: str, functionName: str) -> str:
    """Generate basic test cases for a given function (returns test code as string)."""
    try:
        return f"# Auto-generated test cases for {functionName}\nimport pytest\n\ndef test_{functionName}_basic():\n    pass\n"
    except Exception as e:
        logger.error(f"testCaseGenerator failed functionName={functionName!r}: {e}")
        return f"testCaseGenerator error: {e}"


@tool
async def invokeBrowserAgent(task: str, taskId: str = "", userId: str = "") -> str:
    """Invoke the BrowserAgent subgraph to perform browser-based testing or interaction."""
    try:
        from modules.agents.subAgents.browserAgent import runBrowserAgent
        result = await runBrowserAgent(task=task, taskId=taskId, userId=userId)
        return result
    except Exception as e:
        logger.error(f"invokeBrowserAgent failed task={task!r} taskId={taskId}: {e}")
        return f"invokeBrowserAgent error: {e}"
```

### 6.5 `server/modules/agents/tools/browserTools.py`

BrowserAgent tools are thin wrappers over the `mcp__Claude_in_Chrome__*` MCP tool functions. In the FastAPI backend context these are accessed via the MCP client already present in `server/modules/mcp/`. The wrappers normalize the return values to plain strings for LangChain tool compatibility.

```python
from __future__ import annotations

from langchain_core.tools import tool
from config.logger import logger


@tool
async def navigate(url: str, tabId: int = 0) -> str:
    """Navigate the browser to a URL."""
    try:
        from modules.mcp.client import mcpClient
        result = await mcpClient.call("navigate", {"url": url, "tabId": tabId})
        return str(result)
    except Exception as e:
        logger.error(f"browserTools.navigate failed url={url!r}: {e}")
        return f"navigate error: {e}"


@tool
async def click(selector: str, tabId: int = 0) -> str:
    """Click a DOM element by CSS selector."""
    try:
        from modules.mcp.client import mcpClient
        result = await mcpClient.call("left_click", {"selector": selector, "tabId": tabId})
        return str(result)
    except Exception as e:
        logger.error(f"browserTools.click failed selector={selector!r}: {e}")
        return f"click error: {e}"


@tool
async def fill(selector: str, value: str, tabId: int = 0) -> str:
    """Fill an input element with a value."""
    try:
        from modules.mcp.client import mcpClient
        result = await mcpClient.call("form_input", {"ref": selector, "value": value, "tabId": tabId})
        return str(result)
    except Exception as e:
        logger.error(f"browserTools.fill failed selector={selector!r}: {e}")
        return f"fill error: {e}"


@tool
async def screenshot(tabId: int = 0) -> str:
    """Take a screenshot and return a description or path."""
    try:
        from modules.mcp.client import mcpClient
        result = await mcpClient.call("screenshot", {"tabId": tabId})
        return str(result)
    except Exception as e:
        logger.error(f"browserTools.screenshot failed: {e}")
        return f"screenshot error: {e}"


@tool
async def assertPage(expectedText: str, tabId: int = 0) -> str:
    """Assert that expected text is present on the current page."""
    try:
        from modules.mcp.client import mcpClient
        pageText = await mcpClient.call("get_page_text", {"tabId": tabId})
        if expectedText.lower() in str(pageText).lower():
            return f"PASS: '{expectedText}' found on page."
        return f"FAIL: '{expectedText}' not found on page."
    except Exception as e:
        logger.error(f"browserTools.assertPage failed expectedText={expectedText!r}: {e}")
        return f"assertPage error: {e}"


@tool
async def getPageText(tabId: int = 0) -> str:
    """Get the full text content of the current page."""
    try:
        from modules.mcp.client import mcpClient
        result = await mcpClient.call("get_page_text", {"tabId": tabId})
        return str(result)[:8000]
    except Exception as e:
        logger.error(f"browserTools.getPageText failed: {e}")
        return f"getPageText error: {e}"
```

### 6.6 `server/modules/agents/tools/reportTools.py`

```python
from __future__ import annotations

from langchain_core.tools import tool
from config.logger import logger


@tool
async def reportWriter(
    goal: str,
    researchSummary: str,
    planSummary: str,
    implementationSummary: str,
    testingSummary: str,
    status: str,
) -> str:
    """Compose a full Markdown final report from agent outputs."""
    try:
        return f"""# Task Report\n\n**Goal:** {goal}\n\n**Status:** {status}\n\n## Research\n{researchSummary}\n\n## Plan\n{planSummary}\n\n## Implementation\n{implementationSummary}\n\n## Testing\n{testingSummary}\n"""
    except Exception as e:
        logger.error(f"reportWriter failed: {e}")
        return f"reportWriter error: {e}"


@tool
async def summaryGenerator(content: str, maxWords: int = 200) -> str:
    """Generate a concise summary of content (returns first maxWords words as placeholder)."""
    try:
        words = content.split()
        return " ".join(words[:maxWords]) + ("..." if len(words) > maxWords else "")
    except Exception as e:
        logger.error(f"summaryGenerator failed: {e}")
        return f"summaryGenerator error: {e}"
```

- [ ] Create `server/modules/agents/tools/` directory (and `__init__.py`)
- [ ] Create all 5 tool files: `researchTools.py`, `plannerTools.py`, `implementTools.py`, `testingTools.py`, `browserTools.py`, `reportTools.py`
- [ ] Commit:
  ```
  git add server/modules/agents/tools/
  git commit -m "feat: add agent tool implementations (research, planner, implement, testing, browser, report)"
  ```

---

## Task 7: Sub-Agents

**Files to create:** `server/modules/agents/subAgents/` (one file per agent)

Each sub-agent follows this pattern:
1. Receive `TaskState` (passed as a LangGraph node function argument).
2. Load short-term memory (messages from `taskMemory.readMessages(taskId)`).
3. Recall long-term memory (episodic + semantic/procedural via `agentMemory`).
4. Build system prompt with recalled context injected.
5. Call `deepMoryLLM` with tool binding (using `.bind_tools()`).
6. Accumulate streaming output.
7. Write long-term memory after completion.
8. Return updated `TaskState` fields.

### 7.1 Base pattern (to be followed by all sub-agents)

```python
# Template structure â€” each agent file follows this shape

from __future__ import annotations

import time
from typing import Any

from langchain_core.messages import HumanMessage, SystemMessage

from config.logger import logger
from modules.agents.deepMoryLLM import deepMoryLLM
from modules.agents.memory.agentMemory import agentMemory
from modules.agents.memory.taskMemory import taskMemory
from modules.agents.orchestrator.taskState import TaskState
from modules.agents.tools.<toolModule> import tool1, tool2

_AGENT_TYPE = "<agentType>"

_SYSTEM_PROMPT = """You are the <Name> agent in the DeepMory multi-agent system.
...<agent-specific instructions>...
Use available tools to complete your task and return structured results."""


async def <agentName>Node(state: TaskState) -> dict:
    """LangGraph node function for the <Name> Agent."""
    taskId = state["taskId"]
    userId = state["userId"]
    startMs = int(time.time() * 1000)
    try:
        # 1. Load short-term messages
        cachedMessages = await taskMemory.readMessages(taskId)

        # 2. Recall long-term memory
        episodic = await agentMemory.recallEpisodic(_AGENT_TYPE, userId, limit=3)
        semantic = await agentMemory.recallSemantic(userId, state["goal"], limit=3)
        procedural = await agentMemory.recallProcedural(_AGENT_TYPE, state["goal"], limit=3)

        memoryContext = ""
        if episodic:
            memoryContext += "\nPast runs:\n" + "\n".join(f"- {e['content']}" for e in episodic)
        if semantic:
            memoryContext += "\nRelevant knowledge:\n" + "\n".join(f"- {s['content']}" for s in semantic)
        if procedural:
            memoryContext += "\nEffective patterns:\n" + "\n".join(f"- {p['content']}" for p in procedural)

        systemContent = _SYSTEM_PROMPT + (f"\n\nMemory context:{memoryContext}" if memoryContext else "")

        # 3. Build messages array
        messages = [SystemMessage(content=systemContent)] + state["messages"]

        # 4. LLM call with tools bound
        llmWithTools = deepMoryLLM.bind_tools([tool1, tool2])
        response = ""
        async for chunk in llmWithTools._astream(messages):
            response += chunk.message.content

        # 5. Write episodic memory
        await agentMemory.writeEpisodic(
            agentType=_AGENT_TYPE,
            userId=userId,
            taskId=taskId,
            content=f"Goal: {state['goal']} | Output: {response[:500]}",
        )

        # 6. Return updated state fields
        return {
            "<outputField>": {"result": response, "status": "done"},
            "currentAgent": _AGENT_TYPE,
            "iterationCount": state["iterationCount"] + 1,
        }
    except Exception as e:
        logger.error(f"{_AGENT_TYPE}Node failed taskId={taskId} userId={userId}: {e}")
        return {
            "status": "failed",
            "errorMessage": f"{_AGENT_TYPE} failed: {e}",
            "currentAgent": _AGENT_TYPE,
        }
```

### 7.2 Individual agent files

**`server/modules/agents/subAgents/researchAgent.py`**
- `_AGENT_TYPE = "research"`
- Tools: `webSearch`, `ragSearch`, `documentReader`
- Output field: `researchFindings` (list of dicts appended)
- Post-run: write semantic memory with key findings

**`server/modules/agents/subAgents/plannerAgent.py`**
- `_AGENT_TYPE = "planner"`
- Tools: `createPlan`, `validatePlan`
- Output field: `plan` (dict)
- Post-run: write procedural memory with the plan structure if successful

**`server/modules/agents/subAgents/implementAgent.py`**
- `_AGENT_TYPE = "implement"`
- Tools: `codeWriter`, `fileWriter`, `shellRunner`
- Output field: `implementationResult` (dict with `status`, `files`, `output`)
- Post-run: write procedural memory with tech stack choices used

**`server/modules/agents/subAgents/testingAgent.py`**
- `_AGENT_TYPE = "testing"`
- Tools: `codeRunner`, `testRunner`, `validator`, `testCaseGenerator`, `invokeBrowserAgent`
- Output field: `testingResult` (dict with `passed: bool`, `details`)
- Post-run: write episodic memory with failure patterns if tests failed

**`server/modules/agents/subAgents/reportAgent.py`**
- `_AGENT_TYPE = "report"`
- Tools: `reportWriter`, `summaryGenerator`
- Output field: `finalReport` (string Markdown)
- Post-run: write procedural memory with report format preferences

**`server/modules/agents/subAgents/browserAgent.py`**
- `_AGENT_TYPE = "browser"`
- Tools: `navigate`, `click`, `fill`, `screenshot`, `assertPage`, `getPageText`
- Implements `runBrowserAgent(task, taskId, userId) -> str` (called by `invokeBrowserAgent` tool)
- Post-run: write episodic memory with tested UI flows
- Also exposes `browserAgentNode(state)` for use as a standalone graph node when invoked via `/browser` slash command

- [ ] Create `server/modules/agents/subAgents/` directory (and `__init__.py`)
- [ ] Create `researchAgent.py`, `plannerAgent.py`, `implementAgent.py`, `testingAgent.py`, `reportAgent.py`, `browserAgent.py`
- [ ] Commit:
  ```
  git add server/modules/agents/subAgents/
  git commit -m "feat: add 6 sub-agent node implementations (research, planner, implement, testing, browser, report)"
  ```

---

## Task 8: Supervisor + Graph Builder

**Files to create:**
- `server/modules/agents/orchestrator/supervisorAgent.py`
- `server/modules/agents/orchestrator/graphBuilder.py`

### 8.1 supervisorAgent.py

The Supervisor is a LangGraph node that receives `TaskState`, calls `deepMoryLLM._agenerate()` (non-streaming) with a single tool `routeToAgent`, parses the tool call response, and updates `nextAgent`.

```python
from __future__ import annotations

import json
import os
from typing import Literal

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.tools import tool

from config.logger import logger
from modules.agents.deepMoryLLM import deepMoryLLM
from modules.agents.orchestrator.taskState import TaskState

_SUPERVISOR_SYSTEM = """You are the Supervisor of the DeepMory multi-agent system.
Your only job is to decide which agent should act next based on the current TaskState.
You MUST call the routeToAgent tool with the name of the next agent.

Routing rules (use LLM judgment, not hardcoded logic):
- No research yet â†’ route to 'research'
- Research done, no plan â†’ route to 'planner'
- Plan done, no implementation â†’ route to 'implement'
- Implementation done, no testing â†’ route to 'testing'
- Testing passed â†’ route to 'report'
- Testing failed and iterations < maxIterations â†’ route to 'implement'
- Testing failed and iterations >= maxIterations â†’ route to 'report' (partial failure)
- Report done â†’ route to '__end__'
Valid agent names: research, planner, implement, testing, report, __end__
"""


@tool
def routeToAgent(agentName: str) -> str:
    """Route the task to a specific agent or end the pipeline."""
    return agentName


async def supervisorNode(state: TaskState) -> dict:
    """Supervisor LangGraph node â€” decides next agent via non-streaming LLM call."""
    taskId = state["taskId"]
    try:
        stateContext = json.dumps({
            "goal": state["goal"],
            "iterationCount": state["iterationCount"],
            "maxIterations": state["maxIterations"],
            "researchDone": bool(state.get("researchFindings")),
            "planDone": state.get("plan") is not None,
            "implementDone": state.get("implementationResult") is not None,
            "testingDone": state.get("testingResult") is not None,
            "testingPassed": state.get("testingResult", {}).get("passed", False) if state.get("testingResult") else False,
            "reportDone": state.get("finalReport") is not None,
            "status": state["status"],
        }, indent=2)

        messages = [
            SystemMessage(content=_SUPERVISOR_SYSTEM),
            HumanMessage(content=f"Current TaskState:\n{stateContext}\n\nDecide which agent to invoke next."),
        ]

        llmWithRoute = deepMoryLLM.bind_tools([routeToAgent])
        result = await llmWithRoute._agenerate(messages)
        aiMessage = result.generations[0].message

        nextAgent = "__end__"
        if hasattr(aiMessage, "tool_calls") and aiMessage.tool_calls:
            toolCall = aiMessage.tool_calls[0]
            nextAgent = toolCall.get("args", {}).get("agentName", "__end__")
        else:
            content = aiMessage.content.strip().lower()
            for name in ("research", "planner", "implement", "testing", "report"):
                if name in content:
                    nextAgent = name
                    break

        logger.info(f"supervisorNode taskId={taskId} â†’ nextAgent={nextAgent} iter={state['iterationCount']}")
        return {"nextAgent": nextAgent, "currentAgent": "supervisor"}
    except Exception as e:
        logger.error(f"supervisorNode failed taskId={taskId}: {e}")
        return {"nextAgent": "__end__", "status": "failed", "errorMessage": f"Supervisor error: {e}"}
```

### 8.2 graphBuilder.py

```python
from __future__ import annotations

from typing import Annotated
from typing_extensions import TypedDict

from langchain_core.messages import BaseMessage
from langgraph.graph import StateGraph, END
from langgraph.graph.message import add_messages

from modules.agents.memory.taskMemory import taskMemory
from modules.agents.orchestrator.supervisorAgent import supervisorNode
from modules.agents.orchestrator.taskState import TaskState
from modules.agents.subAgents.browserAgent import browserAgentNode
from modules.agents.subAgents.implementAgent import implementNode
from modules.agents.subAgents.plannerAgent import plannerNode
from modules.agents.subAgents.reportAgent import reportNode
from modules.agents.subAgents.researchAgent import researchNode
from modules.agents.subAgents.testingAgent import testingNode


class AgentGraphState(TypedDict):
    """LangGraph-compatible state with Annotated messages for auto-appending."""
    taskId: str
    userId: str
    conversationId: str | None
    projectId: str | None
    currentAgent: str
    nextAgent: str | None
    iterationCount: int
    maxIterations: int
    status: str
    errorMessage: str | None
    messages: Annotated[list[BaseMessage], add_messages]
    goal: str
    researchFindings: list[dict]
    plan: dict | None
    implementationResult: dict | None
    testingResult: dict | None
    finalReport: str | None


def _routeFromSupervisor(state: AgentGraphState) -> str:
    """Conditional edge: reads nextAgent set by supervisorNode."""
    nextAgent = state.get("nextAgent", "__end__")
    if nextAgent == "__end__" or state.get("status") in ("failed", "cancelled"):
        return END
    return nextAgent


def buildGraph():
    """Build and compile the DeepMory agent StateGraph."""
    graph = StateGraph(AgentGraphState)

    graph.add_node("supervisor", supervisorNode)
    graph.add_node("research", researchNode)
    graph.add_node("planner", plannerNode)
    graph.add_node("implement", implementNode)
    graph.add_node("testing", testingNode)
    graph.add_node("browser", browserAgentNode)
    graph.add_node("report", reportNode)

    graph.set_entry_point("supervisor")

    graph.add_conditional_edges(
        "supervisor",
        _routeFromSupervisor,
        {
            "research": "research",
            "planner": "planner",
            "implement": "implement",
            "testing": "testing",
            "browser": "browser",
            "report": "report",
            END: END,
        },
    )

    for agentNode in ("research", "planner", "implement", "testing", "browser", "report"):
        graph.add_edge(agentNode, "supervisor")

    compiled = graph.compile(checkpointer=taskMemory)
    return compiled


agentGraph = buildGraph()
```

- [ ] Create `server/modules/agents/orchestrator/supervisorAgent.py`
- [ ] Create `server/modules/agents/orchestrator/graphBuilder.py`
- [ ] Verify the graph compiles: `python -c "from modules.agents.orchestrator.graphBuilder import agentGraph; print('OK')"`
- [ ] Commit:
  ```
  git add server/modules/agents/orchestrator/
  git commit -m "feat: add Supervisor node and LangGraph StateGraph builder with conditional routing"
  ```

---

## Task 9: Repository + Service

**Files to create:**
- `server/modules/agents/repository.py`
- `server/modules/agents/service.py`

### 9.1 repository.py

CRUD for `agentTasks`, `agentRuns`, and `agentMemories`. Dual-mode: PostgreSQL when available, JSON file fallback.

```python
from __future__ import annotations

import json
import uuid
from datetime import datetime
from typing import Dict, List, Optional

from config.database import db
from config.logger import logger


class AgentRepository:

    async def createTask(
        self,
        userId: str,
        goal: str,
        conversationId: Optional[str] = None,
        projectId: Optional[str] = None,
    ) -> Dict:
        taskId = str(uuid.uuid4())
        try:
            if db.useDatabase and db.pool:
                async with db.pool.acquire() as conn:
                    row = await conn.fetchrow(
                        """INSERT INTO "agentTasks"
                           ("id","userId","conversationId","projectId","goal","status")
                           VALUES ($1,$2,$3,$4,$5,'running')
                           RETURNING *""",
                        taskId, userId, conversationId, projectId, goal,
                    )
                    return dict(row)
            else:
                task = {"id": taskId, "userId": userId, "goal": goal, "status": "running",
                        "conversationId": conversationId, "projectId": projectId,
                        "createdAt": datetime.utcnow().isoformat()}
                data = db.read_json("agentTasks")
                if not isinstance(data, list):
                    data = []
                data.append(task)
                db.write_json("agentTasks", data)
                return task
        except Exception as e:
            logger.error(f"AgentRepository.createTask failed userId={userId} goal={goal!r}: {e}")
            raise

    async def updateTaskStatus(
        self, taskId: str, status: str,
        finalReport: Optional[str] = None,
        errorMessage: Optional[str] = None,
    ) -> None:
        try:
            if db.useDatabase and db.pool:
                async with db.pool.acquire() as conn:
                    await conn.execute(
                        """UPDATE "agentTasks"
                           SET "status"=$2, "finalReport"=$3, "errorMessage"=$4, "updatedAt"=now()
                           WHERE "id"=$1""",
                        taskId, status, finalReport, errorMessage,
                    )
        except Exception as e:
            logger.error(f"AgentRepository.updateTaskStatus failed taskId={taskId}: {e}")

    async def getTask(self, taskId: str) -> Optional[Dict]:
        try:
            if db.useDatabase and db.pool:
                async with db.pool.acquire() as conn:
                    row = await conn.fetchrow(
                        """SELECT * FROM "agentTasks" WHERE "id"=$1""", taskId
                    )
                    return dict(row) if row else None
        except Exception as e:
            logger.error(f"AgentRepository.getTask failed taskId={taskId}: {e}")
        return None

    async def listTasks(self, userId: str, limit: int = 20) -> List[Dict]:
        try:
            if db.useDatabase and db.pool:
                async with db.pool.acquire() as conn:
                    rows = await conn.fetch(
                        """SELECT * FROM "agentTasks" WHERE "userId"=$1
                           ORDER BY "createdAt" DESC LIMIT $2""",
                        userId, limit,
                    )
                    return [dict(r) for r in rows]
        except Exception as e:
            logger.error(f"AgentRepository.listTasks failed userId={userId}: {e}")
        return []

    async def createRun(
        self, taskId: str, agentType: str, iterationNum: int,
        inputData: Optional[Dict] = None,
    ) -> str:
        runId = str(uuid.uuid4())
        try:
            if db.useDatabase and db.pool:
                async with db.pool.acquire() as conn:
                    await conn.execute(
                        """INSERT INTO "agentRuns"
                           ("id","taskId","agentType","iterationNum","input","status")
                           VALUES ($1,$2,$3,$4,$5,'running')""",
                        runId, taskId, agentType, iterationNum,
                        json.dumps(inputData or {}),
                    )
        except Exception as e:
            logger.error(f"AgentRepository.createRun failed taskId={taskId} agentType={agentType}: {e}")
        return runId

    async def updateRun(
        self, runId: str, status: str, outputData: Optional[Dict] = None, durationMs: Optional[int] = None
    ) -> None:
        try:
            if db.useDatabase and db.pool:
                async with db.pool.acquire() as conn:
                    await conn.execute(
                        """UPDATE "agentRuns"
                           SET "status"=$2,"output"=$3,"durationMs"=$4 WHERE "id"=$1""",
                        runId, status, json.dumps(outputData or {}), durationMs,
                    )
        except Exception as e:
            logger.error(f"AgentRepository.updateRun failed runId={runId}: {e}")

    async def listRuns(self, taskId: str) -> List[Dict]:
        try:
            if db.useDatabase and db.pool:
                async with db.pool.acquire() as conn:
                    rows = await conn.fetch(
                        """SELECT * FROM "agentRuns" WHERE "taskId"=$1
                           ORDER BY "createdAt" ASC""",
                        taskId,
                    )
                    return [dict(r) for r in rows]
        except Exception as e:
            logger.error(f"AgentRepository.listRuns failed taskId={taskId}: {e}")
        return []

    async def listMemories(self, userId: str, limit: int = 50) -> List[Dict]:
        try:
            if db.useDatabase and db.pool:
                async with db.pool.acquire() as conn:
                    rows = await conn.fetch(
                        """SELECT * FROM "agentMemories" WHERE "userId"=$1
                           ORDER BY "createdAt" DESC LIMIT $2""",
                        userId, limit,
                    )
                    return [dict(r) for r in rows]
        except Exception as e:
            logger.error(f"AgentRepository.listMemories failed userId={userId}: {e}")
        return []


agentRepository = AgentRepository()
```

### 9.2 service.py â€” AgentFacade

```python
from __future__ import annotations

import asyncio
import json
import time
import uuid
from typing import AsyncGenerator, Dict, Optional

from config.logger import logger
from modules.agents.memory.agentMemory import agentMemory
from modules.agents.orchestrator.graphBuilder import agentGraph
from modules.agents.orchestrator.taskState import buildInitialState
from modules.agents.repository import agentRepository

_SLASH_COMMAND_MAP = {
    "/research": "research",
    "/plan": "planner",
    "/implement": "implement",
    "/report": "report",
    "/run": None,
    "/browser": "browser",
}


class AgentFacade:

    async def createTask(
        self,
        userId: str,
        goal: str,
        conversationId: Optional[str] = None,
        projectId: Optional[str] = None,
    ) -> Dict:
        """Create a task record and return it. Does NOT start the graph yet."""
        try:
            return await agentRepository.createTask(userId, goal, conversationId, projectId)
        except Exception as e:
            logger.error(f"AgentFacade.createTask failed userId={userId} goal={goal!r}: {e}")
            raise

    async def runFromCommand(
        self, userId: str, conversationId: str, command: str
    ) -> Dict:
        """Parse a slash command and start the agent task. Returns task dict immediately."""
        try:
            parts = command.strip().split(None, 1)
            prefix = parts[0].lower()
            goalText = parts[1] if len(parts) > 1 else ""

            if prefix not in _SLASH_COMMAND_MAP:
                prefix = "/run"
                goalText = command

            task = await agentRepository.createTask(userId, goalText, conversationId)
            asyncio.create_task(self._runGraph(task["id"], userId, goalText, conversationId))
            return task
        except Exception as e:
            logger.error(f"AgentFacade.runFromCommand failed userId={userId} command={command!r}: {e}")
            raise

    async def cancelTask(self, taskId: str) -> bool:
        """Cancel a running task."""
        try:
            await agentRepository.updateTaskStatus(taskId, "cancelled")
            return True
        except Exception as e:
            logger.error(f"AgentFacade.cancelTask failed taskId={taskId}: {e}")
            return False

    async def streamTask(self, taskId: str) -> AsyncGenerator[str, None]:
        """SSE generator yielding agent run events for a task."""
        try:
            lastRunCount = 0
            maxPolls = 600
            for _ in range(maxPolls):
                task = await agentRepository.getTask(taskId)
                runs = await agentRepository.listRuns(taskId)

                for run in runs[lastRunCount:]:
                    event = {"type": "agentRun", "run": run}
                    yield f"data: {json.dumps(event, default=str)}\n\n"
                lastRunCount = len(runs)

                if task and task["status"] in ("completed", "failed", "partial_failure", "cancelled"):
                    yield f"data: {json.dumps({'type': 'done', 'task': task}, default=str)}\n\n"
                    break

                await asyncio.sleep(0.5)
        except Exception as e:
            logger.error(f"AgentFacade.streamTask failed taskId={taskId}: {e}")
            yield f"data: {json.dumps({'type': 'error', 'message': str(e)})}\n\n"

    async def _runGraph(
        self,
        taskId: str,
        userId: str,
        goal: str,
        conversationId: Optional[str] = None,
        projectId: Optional[str] = None,
    ) -> None:
        """Background task: run the LangGraph pipeline end-to-end."""
        try:
            initialState = buildInitialState(taskId, userId, goal, conversationId, projectId)
            config = {"configurable": {"thread_id": taskId}}
            finalState = await agentGraph.ainvoke(initialState, config=config)

            status = finalState.get("status", "completed")
            finalReport = finalState.get("finalReport")
            errorMessage = finalState.get("errorMessage")

            await agentRepository.updateTaskStatus(taskId, status, finalReport, errorMessage)

            if finalReport and conversationId:
                try:
                    from modules.message.repository import messageRepository
                    await messageRepository.create(conversationId, "assistant", finalReport)
                except Exception as postErr:
                    logger.warning(f"AgentFacade._runGraph failed to post report to conversation: {postErr}")
        except Exception as e:
            logger.error(f"AgentFacade._runGraph failed taskId={taskId} userId={userId}: {e}")
            await agentRepository.updateTaskStatus(taskId, "failed", errorMessage=str(e))


agentService = AgentFacade()
```

- [ ] Create `server/modules/agents/repository.py`
- [ ] Create `server/modules/agents/service.py`
- [ ] Commit:
  ```
  git add server/modules/agents/repository.py server/modules/agents/service.py
  git commit -m "feat: add AgentRepository (CRUD) and AgentFacade service with graph orchestration"
  ```

---

## Task 10: Router + API Integration

**Files to create:** `server/modules/agents/router.py`
**Files to modify:**
- `server/modules/message/router.py` â€” add slash command detection before `messageService`
- `server/apiRouter.py` â€” register agents router

### 10.1 `server/modules/agents/router.py`

```python
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import Dict, Optional

from common.deps import getCurrentUser
from config.logger import logger
from modules.agents.memory.agentMemory import agentMemory
from modules.agents.repository import agentRepository
from modules.agents.service import agentService

router = APIRouter(prefix="/agents", tags=["Agents"])


class TaskCreateRequest(BaseModel):
    goal: str
    conversationId: Optional[str] = None
    projectId: Optional[str] = None


@router.post("/tasks")
async def createTask(body: TaskCreateRequest, user: Dict = Depends(getCurrentUser)):
    try:
        task = await agentService.createTask(
            userId=str(user["id"]),
            goal=body.goal,
            conversationId=body.conversationId,
            projectId=body.projectId,
        )
        return task
    except Exception as e:
        logger.error(f"POST /agents/tasks failed userId={user['id']}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/tasks")
async def listTasks(user: Dict = Depends(getCurrentUser)):
    try:
        return await agentRepository.listTasks(str(user["id"]))
    except Exception as e:
        logger.error(f"GET /agents/tasks failed userId={user['id']}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/tasks/{taskId}")
async def getTask(taskId: str, user: Dict = Depends(getCurrentUser)):
    try:
        task = await agentRepository.getTask(taskId)
        if not task:
            raise HTTPException(status_code=404, detail="Task not found")
        runs = await agentRepository.listRuns(taskId)
        return {**task, "runs": runs}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"GET /agents/tasks/{taskId} failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/tasks/{taskId}")
async def cancelTask(taskId: str, user: Dict = Depends(getCurrentUser)):
    try:
        success = await agentService.cancelTask(taskId)
        return {"cancelled": success}
    except Exception as e:
        logger.error(f"DELETE /agents/tasks/{taskId} failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/tasks/{taskId}/stream")
async def streamTask(taskId: str, user: Dict = Depends(getCurrentUser)):
    try:
        return StreamingResponse(
            agentService.streamTask(taskId),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "Connection": "keep-alive"},
        )
    except Exception as e:
        logger.error(f"GET /agents/tasks/{taskId}/stream failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/memories")
async def listMemories(user: Dict = Depends(getCurrentUser)):
    try:
        return await agentRepository.listMemories(str(user["id"]))
    except Exception as e:
        logger.error(f"GET /agents/memories failed userId={user['id']}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/memories/{memoryId}")
async def deleteMemory(memoryId: str, user: Dict = Depends(getCurrentUser)):
    try:
        success = await agentMemory.deleteMemory(memoryId)
        if not success:
            raise HTTPException(status_code=404, detail="Memory not found")
        return {"deleted": True}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"DELETE /agents/memories/{memoryId} failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))
```

### 10.2 Modify `server/modules/message/router.py`

Add slash command detection to the `sendMessageStream` handler. Insert the following block **before** the existing `validation = messageService.validateMessage(...)` line:

```python
# At the top of the file, add import:
from modules.agents.service import agentService

# In sendMessageStream, add at the beginning of the try block:
if data.message.strip().startswith("/"):
    try:
        task = await agentService.runFromCommand(
            str(user["id"]), data.conversationId, data.message.strip()
        )
        return {"taskId": task["id"], "streaming": True}
    except Exception as e:
        logger.error(f"Slash command routing failed userId={user['id']} cmd={data.message!r}: {e}")
        raise HTTPException(status_code=500, detail=str(e))
```

The full modified `sendMessageStream` function becomes:

```python
@router.post("/chat/completions")
async def sendMessageStream(data: MessageRequest, user: Dict = Depends(getCurrentUser)):
    try:
        if data.message.strip().startswith("/"):
            try:
                task = await agentService.runFromCommand(
                    str(user["id"]), data.conversationId, data.message.strip()
                )
                return {"taskId": task["id"], "streaming": True}
            except Exception as e:
                logger.error(f"Slash command routing failed userId={user['id']} cmd={data.message!r}: {e}")
                raise HTTPException(status_code=500, detail=str(e))

        validation = messageService.validateMessage(data.message)
        if not validation['valid']:
            raise HTTPException(status_code=400, detail={"errors": validation['errors']})

        async def eventGenerator():
            fullResponse = ""
            try:
                async for chunk in messageService.processMessageFlow(
                    str(user['id']),
                    data.conversationId,
                    data.message,
                    data.projectId
                ):
                    fullResponse += chunk
                    yield f"data: {json.dumps({'chunk': chunk})}\n\n"
                yield f"data: {json.dumps({'done': True, 'fullResponse': fullResponse})}\n\n"
            except Exception as e:
                logger.error(f"Streaming error: {e}")
                yield f"data: {json.dumps({'error': str(e)})}\n\n"

        return StreamingResponse(
            eventGenerator(),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "Connection": "keep-alive"},
        )
    except Exception as e:
        logger.error(f"Error streaming message: {e}")
        raise HTTPException(status_code=500, detail=str(e))
```

### 10.3 Modify `server/apiRouter.py`

Add the agents router import and include statement:

```python
from modules.agents.router import router as agentsRouter

# After existing router.include_router(memoryRouter):
router.include_router(agentsRouter)
```

### 10.4 Add environment variables to `server/.env.example`

```
AGENT_MAX_ITERATIONS=10
AGENT_WORKSPACE_DIR=./agent_workspace
AGENT_SHELL_TIMEOUT=30
TAVILY_API_KEY=
AGENT_EMBEDDING_DIM=1536
AGENT_CHECKPOINT_TTL=86400
```

- [ ] Create `server/modules/agents/router.py`
- [ ] Modify `server/modules/message/router.py` to add slash command detection
- [ ] Modify `server/apiRouter.py` to register agents router
- [ ] Update `server/.env.example` with agent environment variables
- [ ] Start the server and verify `GET /api/v1/agents/tasks` returns 200 (or 401 without auth)
- [ ] Commit:
  ```
  git add server/modules/agents/router.py server/modules/message/router.py server/apiRouter.py server/.env.example
  git commit -m "feat: add agents router (7 endpoints + SSE), slash command routing, and API registration"
  ```

---

## Dependency Graph

```
Task 1 (deps)
  â””â”€ Task 2 (migration)
       â””â”€ Task 3 (DeepMoryLLM)
            â””â”€ Task 4 (TaskState)
                 â””â”€ Task 5 (Memory)
                      â””â”€ Task 6 (Tools)
                           â””â”€ Task 7 (Sub-Agents)
                                â””â”€ Task 8 (Supervisor + Graph)
                                     â””â”€ Task 9 (Repository + Service)
                                          â””â”€ Task 10 (Router + Integration)
```

Each task depends on all prior tasks. Tasks 6 sub-modules (individual tool files) can be parallelized within Task 6.

---

## Environment Variables Summary

| Variable | Default | Required | Description |
|---|---|---|---|
| `AGENT_MAX_ITERATIONS` | `10` | No | Supervisor max routing iterations per task |
| `AGENT_WORKSPACE_DIR` | `./agent_workspace` | No | shellRunner / fileWriter working directory |
| `AGENT_SHELL_TIMEOUT` | `30` | No | shellRunner hard timeout in seconds |
| `TAVILY_API_KEY` | â€” | Yes (Research Agent) | Tavily Search API key |
| `AGENT_EMBEDDING_DIM` | `1536` | No | Vector dimension for Qdrant agent collections |
| `AGENT_CHECKPOINT_TTL` | `86400` | No | Redis checkpoint TTL in seconds (24h) |
| `QDRANT_URL` | `http://localhost:6333` | No | Qdrant instance URL for agent memory |

---

## Error Handling Notes

- Every `try/except` block logs with `logger.error(f"<functionName> failed <context>: {e}")` and then either raises or returns a safe default.
- Background tasks (`asyncio.create_task`) never re-raise â€” they log the error and return silently.
- The `_runGraph` background task in `service.py` always calls `agentRepository.updateTaskStatus(taskId, "failed", ...)` on any unhandled exception so the frontend receives a terminal state.
- Supervisor and sub-agents return `{"status": "failed", "errorMessage": ...}` state updates on exception rather than crashing the graph.
- Redis unavailable: `cacheService.get/set` return `None`/no-op (see existing `cacheService.py`). `RedisCheckpointer` falls back gracefully returning `None` from `aget`.

---

## Critical Files for Implementation

- `/D:/Work/VTC_Telecom/AI_Tutor/ai-tutor-web/server/modules/llm/llmProvider.py` - Core logic to wrap: `LLMInferenceService.generateResponse()` and `streamResponse()` are the exact signatures `DeepMoryLLM` must call
- `/D:/Work/VTC_Telecom/AI_Tutor/ai-tutor-web/server/modules/message/router.py` - The `sendMessageStream` handler must be modified to intercept `/`-prefixed messages and route to `agentService.runFromCommand()`
- `/D:/Work/VTC_Telecom/AI_Tutor/ai-tutor-web/server/apiRouter.py` - Single registration point where the new `agentsRouter` must be added
- `/D:/Work/VTC_Telecom/AI_Tutor/ai-tutor-web/server/migrations/002_memory_rag.sql` - Pattern to follow exactly for `003_agent_system.sql` (camelCase quoted columns, `gen_random_uuid()`, `TIMESTAMPTZ`, REFERENCES pattern)
- `/D:/Work/VTC_Telecom/AI_Tutor/ai-tutor-web/server/modules/memory/shortTerm/repository.py` - Gold standard Redis + PostgreSQL dual-mode repository pattern to replicate in `agentRepository.py` and `RedisCheckpointer`

---

**Important note on file creation:** The `docs/superpowers/plans/` directory does not yet exist. You will need to create it before saving this plan file:

```bash
mkdir -p "D:/Work/VTC_Telecom/AI_Tutor/ai-tutor-web/docs/superpowers/plans"
```

Then save this content to:
`D:/Work/VTC_Telecom/AI_Tutor/ai-tutor-web/docs/superpowers/plans/2026-03-29-multi-agent-system.md`