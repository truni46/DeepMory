from __future__ import annotations

import asyncio
import time
from typing import Any, AsyncGenerator, Dict, Optional

from config.logger import logger
from modules.agents.orchestrator.graphBuilder import agentGraph
from modules.agents.orchestrator.taskState import buildInitialState
from modules.agents.repository import agentRepository

_COMMAND_MAP = {
    "/research": "research",
    "/plan": "plan",
    "/implement": "implement",
    "/report": "report",
    "/run": "run",
    "/browser": "browser",
}


class AgentFacade:
    """Single entry point for all agent operations."""

    async def createTask(
        self,
        userId: str,
        goal: str,
        conversationId: Optional[str] = None,
        projectId: Optional[str] = None,
    ) -> Dict:
        """Create and immediately start a new agent task."""
        try:
            task = await agentRepository.createTask(userId, goal, conversationId, projectId)
            asyncio.create_task(self._runGraph(task["id"], userId, goal, conversationId, projectId))
            return task
        except Exception as e:
            logger.error(f"AgentFacade.createTask failed userId={userId}: {e}")
            raise

    async def runFromCommand(
        self,
        userId: str,
        conversationId: Optional[str],
        command: str,
    ) -> Dict:
        """Parse a slash command and start the appropriate agent task."""
        try:
            parts = command.strip().split(None, 1)
            cmd = parts[0].lower()
            arg = parts[1] if len(parts) > 1 else ""

            if cmd not in _COMMAND_MAP:
                return {"error": f"Unknown command: {cmd}"}

            goal = f"{_COMMAND_MAP[cmd]}: {arg}" if arg else _COMMAND_MAP[cmd]
            return await self.createTask(userId, goal, conversationId)
        except Exception as e:
            logger.error(f"AgentFacade.runFromCommand failed userId={userId} command={command}: {e}")
            raise

    async def getTask(self, taskId: str, userId: str) -> Optional[Dict]:
        try:
            task = await agentRepository.getTask(taskId, userId)
            if task:
                task["runs"] = await agentRepository.getTaskRuns(taskId)
            return task
        except Exception as e:
            logger.error(f"AgentFacade.getTask failed taskId={taskId}: {e}")
            return None

    async def listTasks(self, userId: str) -> list:
        try:
            return await agentRepository.listTasks(userId)
        except Exception as e:
            logger.error(f"AgentFacade.listTasks failed userId={userId}: {e}")
            return []

    async def cancelTask(self, taskId: str, userId: str) -> bool:
        try:
            await agentRepository.updateTask(taskId, {"status": "cancelled"})
            return True
        except Exception as e:
            logger.error(f"AgentFacade.cancelTask failed taskId={taskId}: {e}")
            return False

    async def streamTask(self, taskId: str, userId: str) -> AsyncGenerator[str, None]:
        """SSE generator: streams agent run events for a task."""
        try:
            import json
            lastRunCount = 0
            maxPolls = 120
            for _ in range(maxPolls):
                task = await agentRepository.getTask(taskId, userId)
                if not task:
                    yield f"data: {json.dumps({'error': 'Task not found'})}\n\n"
                    return
                runs = await agentRepository.getTaskRuns(taskId)
                newRuns = runs[lastRunCount:]
                for run in newRuns:
                    event = {
                        "type": "agent_run",
                        "agentType": run.get("agentType"),
                        "status": run.get("status"),
                        "output": run.get("output"),
                    }
                    yield f"data: {json.dumps(event, default=str)}\n\n"
                lastRunCount = len(runs)
                status = task.get("status", "running")
                if status in ("completed", "failed", "partial_failure", "cancelled"):
                    yield f"data: {json.dumps({'type': 'done', 'status': status, 'finalReport': task.get('finalReport')})}\n\n"
                    return
                await asyncio.sleep(1)
        except Exception as e:
            logger.error(f"AgentFacade.streamTask failed taskId={taskId}: {e}")

    async def _runGraph(
        self,
        taskId: str,
        userId: str,
        goal: str,
        conversationId: Optional[str],
        projectId: Optional[str],
    ) -> None:
        """Background task: runs the LangGraph graph and persists results."""
        startTime = time.time()
        try:
            initialState = buildInitialState(taskId, userId, goal, conversationId, projectId)
            config = {"configurable": {"thread_id": taskId}}
            finalState = None
            async for state in agentGraph.astream(initialState, config=config):
                finalState = state
                nodeKey = list(state.keys())[0] if state else None
                if nodeKey:
                    nodeState = state[nodeKey]
                    durationMs = int((time.time() - startTime) * 1000)
                    await agentRepository.createRun(
                        taskId=taskId,
                        agentType=nodeKey,
                        iterationNum=nodeState.get("iterationCount", 0) if isinstance(nodeState, dict) else 0,
                        outputData={"content": str(nodeState.get("messages", [])[-1].content if isinstance(nodeState, dict) and nodeState.get("messages") else "")} if isinstance(nodeState, dict) else {},
                        status="completed",
                        durationMs=durationMs,
                    )
            if finalState:
                lastState = list(finalState.values())[0] if finalState else {}
                if isinstance(lastState, dict):
                    await agentRepository.updateTask(taskId, {
                        "status": lastState.get("status", "completed"),
                        "finalReport": lastState.get("finalReport"),
                        "errorMessage": lastState.get("errorMessage"),
                    })
                else:
                    await agentRepository.updateTask(taskId, {"status": "completed"})
            else:
                await agentRepository.updateTask(taskId, {"status": "completed"})
        except Exception as e:
            logger.error(f"AgentFacade._runGraph failed taskId={taskId}: {e}")
            await agentRepository.updateTask(taskId, {"status": "failed", "errorMessage": str(e)})


agentService = AgentFacade()
