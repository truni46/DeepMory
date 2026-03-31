from __future__ import annotations

from typing import Annotated

from langchain_core.messages import BaseMessage
from langgraph.graph import END, StateGraph
from langgraph.graph.message import add_messages
from typing_extensions import TypedDict

from config.logger import logger
from modules.agents.memory.taskMemory import taskMemory
from modules.agents.orchestrator.supervisorAgent import supervisorNode
from modules.agents.orchestrator.taskState import TaskState
from modules.agents.subAgents.implementAgent import implementNode
from modules.agents.subAgents.plannerAgent import plannerNode
from modules.agents.subAgents.reportAgent import reportNode
from modules.agents.subAgents.researchAgent import researchNode
from modules.agents.subAgents.testingAgent import testingNode


class GraphState(TypedDict):
    """LangGraph state with Annotated messages for proper append semantics."""
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


def _routeFromSupervisor(state: GraphState) -> str:
    """Conditional edge: supervisor's nextAgent decision → actual graph node."""
    nextAgent = state.get("nextAgent", "END")
    routeMap = {
        "research": "research",
        "planner": "planner",
        "implement": "implement",
        "testing": "testing",
        "report": "report",
        "end": END,
        "END": END,
    }
    return routeMap.get(nextAgent, END)


def buildGraph():
    """Build and compile the multi-agent StateGraph with checkpointer."""
    try:
        graph = StateGraph(GraphState)

        graph.add_node("supervisor", supervisorNode)
        graph.add_node("research", researchNode)
        graph.add_node("planner", plannerNode)
        graph.add_node("implement", implementNode)
        graph.add_node("testing", testingNode)
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
                "report": "report",
                END: END,
            },
        )

        for agentName in ("research", "planner", "implement", "testing", "report"):
            graph.add_edge(agentName, "supervisor")

        compiled = graph.compile(checkpointer=taskMemory)
        logger.info("Multi-agent graph compiled with RedisCheckpointer")

        return compiled
    except Exception as e:
        logger.error(f"buildGraph failed: {e}")
        raise


agentGraph = buildGraph()
