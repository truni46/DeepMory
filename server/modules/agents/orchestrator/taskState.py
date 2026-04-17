from __future__ import annotations

import os
from typing import Any, Dict, Literal, Optional

from langchain_core.messages import BaseMessage
from typing_extensions import TypedDict


class TaskState(TypedDict):
    taskId: str
    userId: str
    conversationId: Optional[str]
    projectId: Optional[str]

    currentAgent: str
    nextAgent: Optional[str]
    iterationCount: int
    maxIterations: int
    status: Literal["running", "completed", "failed", "partial_failure", "cancelled"]
    errorMessage: Optional[str]

    messages: list[BaseMessage]
    goal: str
    threadContext: Optional[str]
    agentOutputs: Dict[str, Any]


def buildInitialState(
    taskId: str,
    userId: str,
    goal: str,
    conversationId: Optional[str] = None,
    projectId: Optional[str] = None,
    messages: Optional[list[BaseMessage]] = None,
    threadContext: Optional[str] = None,
) -> TaskState:
    """Construct the initial TaskState for a new agent task."""
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
        messages=messages or [],
        goal=goal,
        threadContext=threadContext,
        agentOutputs={},
    )
