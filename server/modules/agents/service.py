from __future__ import annotations

import asyncio
import time
from typing import Any, AsyncGenerator, Dict, List, Optional

from langchain_core.messages import AIMessage, HumanMessage

from config.logger import logger
from modules.agents.memory.agentMemory import agentMemory
from modules.agents.orchestrator.graphBuilder import agentGraph
from modules.agents.orchestrator.taskState import buildInitialState
from modules.agents.repository import agentRepository
from modules.message.repository import messageRepository

_COMMAND_MAP = {
    "/agents:research": "research",
    "/agents:plan": "plan",
    "/agents:implement": "implement",
    "/agents:report": "report",
    "/agents:browser": "browser",
}

_CHAT_HISTORY_LIMIT = 30


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
                    yield f"data: {json.dumps({'type': 'error', 'message': 'Task not found'})}\n\n"
                    return
                runs = await agentRepository.getTaskRuns(taskId)
                newRuns = runs[lastRunCount:]
                for run in newRuns:
                    outputRaw = run.get("output")
                    if isinstance(outputRaw, str):
                        try:
                            outputRaw = json.loads(outputRaw)
                        except (json.JSONDecodeError, TypeError):
                            pass
                    event = {
                        "type": "agent_run",
                        "agentType": run.get("agentType"),
                        "status": run.get("status"),
                        "output": outputRaw,
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

    async def _loadChatHistory(self, conversationId: str, limit: int = _CHAT_HISTORY_LIMIT) -> List:
        """Load conversation chat history and convert to LangChain messages."""
        try:
            if not conversationId:
                return []
            rows = await messageRepository.getByConversation(conversationId, limit=limit)
            messages = []
            for row in rows:
                role = row.get("role", "")
                content = row.get("content", "")
                if not content:
                    continue
                if role == "user":
                    messages.append(HumanMessage(content=content))
                elif role == "assistant":
                    messages.append(AIMessage(content=content))
            return messages
        except Exception as e:
            logger.error(f"AgentFacade._loadChatHistory failed conversationId={conversationId}: {e}")
            return []

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
            rawHistory = await messageRepository.getByConversation(conversationId, limit=_CHAT_HISTORY_LIMIT) if conversationId else []
            chatHistory = await self._loadChatHistory(conversationId)

            threadContextStr = ""
            if conversationId:
                await agentMemory.compactConversation(conversationId, rawHistory)
                threadContextStr = await agentMemory.getThreadContextString(conversationId)

            initialState = buildInitialState(
                taskId, userId, goal, conversationId, projectId,
                messages=chatHistory,
                threadContext=threadContextStr or None,
            )

            threadId = conversationId or taskId
            config = {"configurable": {"thread_id": threadId}}

            finalState = None
            lastState = {}
            async for state in agentGraph.astream(initialState, config=config):
                finalState = state
            if finalState:
                lastState = list(finalState.values())[0] if finalState else {}
                if isinstance(lastState, dict):
                    finalReport = lastState.get("agentOutputs", {}).get("report", {}).get("content")
                    await agentRepository.updateTask(taskId, {
                        "status": lastState.get("status", "completed"),
                        "finalReport": finalReport,
                        "errorMessage": lastState.get("errorMessage"),
                    })
                    if conversationId:
                        taskSummary = await agentMemory.buildTaskSummary(lastState, taskId, goal)
                        await agentMemory.addTaskToShortTermMemory(conversationId, taskSummary)
                else:
                    await agentRepository.updateTask(taskId, {"status": "completed"})
            else:
                await agentRepository.updateTask(taskId, {"status": "completed"})
        except Exception as e:
            logger.error(f"AgentFacade._runGraph failed taskId={taskId}: {e}")
            await agentRepository.updateTask(taskId, {"status": "failed", "errorMessage": str(e)})


agentService = AgentFacade()
