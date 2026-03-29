from __future__ import annotations

from langchain_core.messages import HumanMessage, SystemMessage

from config.logger import logger
from modules.agents.deepMoryLLM import deepMoryLLM
from modules.agents.memory.agentMemory import agentMemory
from modules.agents.orchestrator.taskState import TaskState
from modules.agents.subAgents.tools import IMPLEMENT_TOOLS


async def implementNode(state: TaskState) -> dict:
    """Implement Agent: executes the plan by writing code or documents."""
    taskId = state["taskId"]
    userId = state["userId"]
    goal = state["goal"]
    plan = state.get("plan") or {}
    iterationCount = state.get("iterationCount", 0)
    testingResult = state.get("testingResult")
    try:
        procedural = await agentMemory.recallProcedural("implement", goal, limit=3)
        proceduralText = "\n".join(f"- {m.get('content', '')}" for m in procedural) or "None"

        retryContext = ""
        if testingResult and iterationCount > 0:
            retryContext = (
                f"\n\nPrevious testing failed. Fix these issues:\n"
                f"{testingResult.get('output', 'Unknown failure')}"
            )

        messages = [
            SystemMessage(content=(
                "You are an Implement Agent. Execute the given plan by writing code or documents. "
                "Use codeWriter for code files, fileWriter for text/markdown, shellRunner to run commands. "
                f"Tech preferences from past work:\n{proceduralText}"
            )),
            HumanMessage(content=(
                f"Goal: {goal}\nPlan: {plan}{retryContext}\n\n"
                "Implement this plan now."
            )),
        ] + list(state.get("messages", []))

        llm = deepMoryLLM.bind_tools(IMPLEMENT_TOOLS)
        response = await llm.ainvoke(messages)

        implementationResult = {
            "output": response.content,
            "iterationCount": iterationCount,
            "toolCalls": [tc.get("name") for tc in (response.tool_calls if hasattr(response, "tool_calls") and response.tool_calls else [])],
        }

        await agentMemory.writeProcedural(
            agentType="implement", userId=userId, taskId=taskId,
            content=f"Implemented: {goal} (iteration {iterationCount})",
            metadata={"goal": goal, "iteration": iterationCount},
        )

        newMessages = list(state.get("messages", [])) + [response]
        return {
            "implementationResult": implementationResult,
            "currentAgent": "implement",
            "iterationCount": iterationCount + 1,
            "messages": newMessages,
        }
    except Exception as e:
        logger.error(f"implementNode failed taskId={taskId}: {e}")
        return {"errorMessage": str(e), "status": "failed"}
