from __future__ import annotations

import os
from typing import Literal, Optional

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
        messages=[],
        goal=goal,
        researchFindings=[],
        plan=None,
        implementationResult=None,
        testingResult=None,
        finalReport=None,
    )
