from __future__ import annotations

import json
import uuid
from typing import Any, Dict, List, Optional

from config.database import db
from config.logger import logger


class AgentRepository:
    """Data access layer for agent tasks, runs, and memories."""

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
                    await conn.execute(
                        """INSERT INTO "agentTasks"
                           ("id","userId","conversationId","projectId","goal","status")
                           VALUES ($1,$2,$3,$4,$5,'running')""",
                        taskId, userId, conversationId, projectId, goal,
                    )
            return {"id": taskId, "userId": userId, "goal": goal, "status": "running"}
        except Exception as e:
            logger.error(f"AgentRepository.createTask failed userId={userId}: {e}")
            return {"id": taskId, "userId": userId, "goal": goal, "status": "running"}

    async def getTask(self, taskId: str, userId: str) -> Optional[Dict]:
        try:
            if db.useDatabase and db.pool:
                async with db.pool.acquire() as conn:
                    row = await conn.fetchrow(
                        'SELECT * FROM "agentTasks" WHERE "id"=$1 AND "userId"=$2',
                        taskId, userId,
                    )
                    if row:
                        return dict(row)
        except Exception as e:
            logger.error(f"AgentRepository.getTask failed taskId={taskId}: {e}")
        return None

    async def listTasks(self, userId: str, limit: int = 20) -> List[Dict]:
        try:
            if db.useDatabase and db.pool:
                async with db.pool.acquire() as conn:
                    rows = await conn.fetch(
                        'SELECT * FROM "agentTasks" WHERE "userId"=$1 ORDER BY "createdAt" DESC LIMIT $2',
                        userId, limit,
                    )
                    return [dict(r) for r in rows]
        except Exception as e:
            logger.error(f"AgentRepository.listTasks failed userId={userId}: {e}")
        return []

    async def updateTask(self, taskId: str, updates: Dict) -> None:
        try:
            if db.useDatabase and db.pool:
                setClauses = ", ".join(f'"{k}"=${i+2}' for i, k in enumerate(updates.keys()))
                values = list(updates.values())
                async with db.pool.acquire() as conn:
                    await conn.execute(
                        f'UPDATE "agentTasks" SET {setClauses} WHERE "id"=$1',
                        taskId, *values,
                    )
        except Exception as e:
            logger.error(f"AgentRepository.updateTask failed taskId={taskId}: {e}")

    async def createRun(
        self,
        taskId: str,
        agentType: str,
        iterationNum: int,
        inputData: Optional[Dict] = None,
        outputData: Optional[Dict] = None,
        status: str = "completed",
        durationMs: Optional[int] = None,
    ) -> str:
        runId = str(uuid.uuid4())
        try:
            if db.useDatabase and db.pool:
                async with db.pool.acquire() as conn:
                    await conn.execute(
                        """INSERT INTO "agentRuns"
                           ("id","taskId","agentType","iterationNum","input","output","status","durationMs")
                           VALUES ($1,$2,$3,$4,$5,$6,$7,$8)""",
                        runId, taskId, agentType, iterationNum,
                        json.dumps(inputData or {}),
                        json.dumps(outputData or {}),
                        status, durationMs,
                    )
        except Exception as e:
            logger.error(f"AgentRepository.createRun failed taskId={taskId}: {e}")
        return runId

    async def getTaskRuns(self, taskId: str) -> List[Dict]:
        try:
            if db.useDatabase and db.pool:
                async with db.pool.acquire() as conn:
                    rows = await conn.fetch(
                        'SELECT * FROM "agentRuns" WHERE "taskId"=$1 ORDER BY "createdAt" ASC',
                        taskId,
                    )
                    return [dict(r) for r in rows]
        except Exception as e:
            logger.error(f"AgentRepository.getTaskRuns failed taskId={taskId}: {e}")
        return []

    async def listMemories(self, userId: str, limit: int = 50) -> List[Dict]:
        try:
            if db.useDatabase and db.pool:
                async with db.pool.acquire() as conn:
                    rows = await conn.fetch(
                        'SELECT * FROM "agentMemories" WHERE "userId"=$1 ORDER BY "createdAt" DESC LIMIT $2',
                        userId, limit,
                    )
                    return [dict(r) for r in rows]
        except Exception as e:
            logger.error(f"AgentRepository.listMemories failed userId={userId}: {e}")
        return []

    async def deleteMemory(self, memoryId: str, userId: str) -> bool:
        try:
            from modules.agents.memory.agentMemory import agentMemory
            return await agentMemory.deleteMemory(memoryId, userId)
        except Exception as e:
            logger.error(f"AgentRepository.deleteMemory failed memoryId={memoryId}: {e}")
        return False


agentRepository = AgentRepository()
