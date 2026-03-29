from __future__ import annotations

from langchain_core.messages import HumanMessage, SystemMessage

from config.logger import logger
from modules.agents.deepMoryLLM import deepMoryLLM
from modules.agents.memory.agentMemory import agentMemory
from modules.agents.orchestrator.taskState import TaskState
from modules.agents.subAgents.tools import REPORT_TOOLS


async def reportNode(state: TaskState) -> dict:
    """Report Agent: synthesizes the full task into a final report."""
    taskId = state["taskId"]
    userId = state["userId"]
    goal = state["goal"]
    testingResult = state.get("testingResult") or {}
    implementationResult = state.get("implementationResult") or {}
    plan = state.get("plan") or {}
    try:
        procedural = await agentMemory.recallProcedural("report", goal, limit=2)
        proceduralText = "\n".join(f"- {m.get('content', '')}" for m in procedural) or "None"

        status = "completed" if testingResult.get("passed") else "partial_failure"

        messages = [
            SystemMessage(content=(
                "You are a Report Agent. Create a comprehensive final report summarizing "
                "what was accomplished, how it was done, and the outcomes. "
                "Use reportWriter to produce a structured markdown report.\n\n"
                f"Report format preferences:\n{proceduralText}"
            )),
            HumanMessage(content=(
                f"Goal: {goal}\n"
                f"Plan: {plan.get('goal', goal)}\n"
                f"Implementation: {implementationResult.get('output', 'N/A')[:300]}\n"
                f"Testing: {'PASSED' if testingResult.get('passed') else 'FAILED'}\n"
                f"Status: {status}\n\n"
                "Write the final report."
            )),
        ] + list(state.get("messages", []))

        llm = deepMoryLLM.bind_tools(REPORT_TOOLS)
        response = await llm.ainvoke(messages)

        await agentMemory.writeProcedural(
            agentType="report", userId=userId, taskId=taskId,
            content=f"Wrote report for: {goal} (status: {status})",
            metadata={"goal": goal, "status": status},
        )

        newMessages = list(state.get("messages", [])) + [response]
        return {
            "finalReport": response.content,
            "status": status,
            "currentAgent": "report",
            "messages": newMessages,
        }
    except Exception as e:
        logger.error(f"reportNode failed taskId={taskId}: {e}")
        return {"errorMessage": str(e), "status": "failed"}
