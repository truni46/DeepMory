from __future__ import annotations

import time

from langchain_core.messages import HumanMessage, SystemMessage
from langchain.agents import create_agent

from config.logger import logger
from modules.agents.deepMoryLLM import deepMoryLLM
from modules.agents.memory.agentMemory import agentMemory
from modules.agents.subAgents.agentUtils import extractLastAIContent, extractConversationContext
from modules.agents.subAgents.taskRunner import taskRunner
from modules.agents.subAgents.tools import IMPLEMENT_TOOLS
from common.prompts import implementSystemPrompt

_reactAgent = create_agent(deepMoryLLM, IMPLEMENT_TOOLS)


async def implementNode(state: dict) -> dict:
    """Implement Agent: dynamically generates implementation tasks, then executes each."""
    taskId = state["taskId"]
    userId = state["userId"]
    goal = state["goal"]
    plan = state.get("agentOutputs", {}).get("planner", {}).get("plan") or {}
    iterationCount = state.get("iterationCount", 0)
    testingResult = state.get("agentOutputs", {}).get("testing", {}).get("result")
    try:
        procedural = await agentMemory.recallProcedural("implement", goal, limit=3)
        proceduralText = "\n".join(f"- {m.get('content', '')}" for m in procedural) or "None"

        retryContext = ""
        if testingResult and iterationCount > 0:
            retryContext = (
                f"\n\nPrevious testing failed. Fix these issues:\n"
                f"{testingResult.get('output', 'Unknown failure')}"
            )

        threadContext = state.get("threadContext") or ""
        conversationMessages = extractConversationContext(state.get("messages", []))

        tasks = await taskRunner.generateTasks("implement", f"{goal}{retryContext}", conversationMessages)
        await taskRunner.reportTasksGenerated(taskId, "implement", tasks)

        allNewMessages = []
        toolsUsed = []

        for i, task in enumerate(tasks):
            await taskRunner.reportTaskStarted(taskId, "implement", i)
            startTime = time.time()

            inputMessages = [
                SystemMessage(content=implementSystemPrompt(proceduralText, threadContext)),
                *conversationMessages,
                HumanMessage(content=(
                    f"Goal: {goal}\nPlan: {plan}\n\n"
                    f"Implementation task: {task['description']}"
                )),
            ]

            result = await _reactAgent.ainvoke(
                {"messages": inputMessages},
                {"recursion_limit": 10},
            )
            newMsgs = result["messages"][len(inputMessages):]
            allNewMessages.extend(newMsgs)

            for msg in newMsgs:
                if getattr(msg, "type", None) == "ai" and hasattr(msg, "tool_calls") and msg.tool_calls:
                    toolsUsed.extend(tc.get("name", "") for tc in msg.tool_calls)

            taskResult = extractLastAIContent(newMsgs)
            durationMs = int((time.time() - startTime) * 1000)
            await taskRunner.reportTaskCompleted(taskId, "implement", i, taskResult, durationMs)

        finalContent = extractLastAIContent(allNewMessages)

        implementationResult = {
            "output": finalContent,
            "iterationCount": iterationCount,
            "toolCalls": toolsUsed,
        }

        await agentMemory.writeProcedural(
            agentType="implement", userId=userId, taskId=taskId,
            content=f"Implemented: {goal} (iteration {iterationCount})",
            metadata={"goal": goal, "iteration": iterationCount},
        )

        return {
            "agentOutputs": {"implement": {"result": implementationResult}},
            "currentAgent": "implement",
            "iterationCount": iterationCount + 1,
            "messages": allNewMessages,
        }
    except Exception as e:
        logger.error(f"implementNode failed taskId={taskId}: {type(e).__name__}: {e}")
        return {"errorMessage": f"{type(e).__name__}: {e}" or "Unknown error", "status": "failed"}
