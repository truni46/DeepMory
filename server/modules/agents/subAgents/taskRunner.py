from __future__ import annotations

import json
import time
from typing import Optional

from langchain_core.messages import BaseMessage

from config.logger import logger
from modules.agents.repository import agentRepository
from modules.llm.llmProvider import llmProvider

_TASK_GEN_PROMPT = (
    "You are a task planner for the {agentType} phase.\n"
    "Given the user's goal and conversation context, generate a concise list of specific tasks "
    "that need to be completed for this phase.\n\n"
    "Rules:\n"
    "- Generate 2-5 tasks maximum\n"
    "- Each task should be actionable and specific\n"
    "- Tasks should be ordered by execution sequence\n"
    "- Respond in pure JSON: {{\"tasks\": [{{\"description\": \"task description\"}}]}}"
)


class TaskRunner:
    """Utility for dynamic task generation and progress reporting within sub-agents."""

    async def generateTasks(
        self,
        agentType: str,
        goal: str,
        conversationContext: Optional[list[BaseMessage]] = None,
        customPrompt: Optional[str] = None,
    ) -> list[dict]:
        """Ask LLM to generate a task list for this agent's specialty."""
        try:
            systemPrompt = customPrompt or _TASK_GEN_PROMPT.format(agentType=agentType)

            contextText = ""
            if conversationContext:
                for msg in conversationContext[-10:]:
                    role = getattr(msg, "type", "unknown")
                    content = str(msg.content)[:200]
                    contextText += f"[{role}]: {content}\n"

            messages = [
                {"role": "system", "content": systemPrompt},
                {"role": "user", "content": f"Goal: {goal}\n\nConversation context:\n{contextText}"},
            ]

            result = await llmProvider.generateResponse(messages, stream=False)
            content = result.content if hasattr(result, "content") else str(result)
            content = content.replace("'''json", "").replace("'''", "").strip()

            data = json.loads(content)
            rawTasks = data.get("tasks", []) if isinstance(data, dict) else data

            return [
                {
                    "index": i,
                    "description": t.get("description", str(t)) if isinstance(t, dict) else str(t),
                    "status": "pending",
                    "result": None,
                }
                for i, t in enumerate(rawTasks)
            ]
        except Exception as e:
            logger.error(f"TaskRunner.generateTasks failed agentType={agentType}: {e}")
            return [{"index": 0, "description": f"Execute {agentType} for: {goal}", "status": "pending", "result": None}]

    async def reportTasksGenerated(self, taskId: str, agentType: str, tasks: list[dict]) -> None:
        """Write task list to DB so frontend can display immediately."""
        try:
            await agentRepository.createRun(
                taskId=taskId,
                agentType=agentType,
                iterationNum=0,
                outputData={"event": "tasks_generated", "tasks": tasks},
                status="processing",
                durationMs=0,
            )
        except Exception as e:
            logger.error(f"TaskRunner.reportTasksGenerated failed taskId={taskId}: {e}")

    async def reportTaskStarted(self, taskId: str, agentType: str, taskIndex: int) -> None:
        """Report that a specific task has started executing."""
        try:
            await agentRepository.createRun(
                taskId=taskId,
                agentType=agentType,
                iterationNum=taskIndex,
                outputData={"event": "task_started", "taskIndex": taskIndex},
                status="processing",
                durationMs=0,
            )
        except Exception as e:
            logger.error(f"TaskRunner.reportTaskStarted failed taskId={taskId} task={taskIndex}: {e}")

    async def reportTaskCompleted(
        self, taskId: str, agentType: str, taskIndex: int, result: str, durationMs: int = 0,
    ) -> None:
        """Report that a specific task has completed."""
        try:
            await agentRepository.createRun(
                taskId=taskId,
                agentType=agentType,
                iterationNum=taskIndex,
                outputData={"event": "task_completed", "taskIndex": taskIndex, "content": result[:500]},
                status="completed",
                durationMs=durationMs,
            )
        except Exception as e:
            logger.error(f"TaskRunner.reportTaskCompleted failed taskId={taskId} task={taskIndex}: {e}")


taskRunner = TaskRunner()
