from __future__ import annotations

import time

from langchain_core.messages import HumanMessage, SystemMessage
from langchain.agents import create_agent

from config.logger import logger
from modules.agents.deepMoryLLM import deepMoryLLM
from modules.agents.memory.agentMemory import agentMemory
from modules.agents.subAgents.agentUtils import extractLastAIContent, extractConversationContext
from modules.agents.subAgents.taskRunner import taskRunner
from modules.agents.subAgents.tools import REPORT_TOOLS
from common.prompts import reportSystemPrompt

_reactAgent = create_agent(deepMoryLLM, REPORT_TOOLS)


async def reportNode(state: dict) -> dict:
    """Report Agent: dynamically generates report tasks, then executes each."""
    taskId = state["taskId"]
    userId = state["userId"]
    goal = state["goal"]
    agentOutputs = state.get("agentOutputs", {})
    testingResult = agentOutputs.get("testing", {}).get("result") or {}
    implementationResult = agentOutputs.get("implement", {}).get("result") or {}
    plan = agentOutputs.get("planner", {}).get("plan") or {}
    try:
        procedural = await agentMemory.recallProcedural("report", goal, limit=2)
        proceduralText = "\n".join(f"- {m.get('content', '')}" for m in procedural) or "None"

        status = "completed" if testingResult.get("passed") else "partial_failure"

        threadContext = state.get("threadContext") or ""
        conversationMessages = extractConversationContext(state.get("messages", []))

        tasks = await taskRunner.generateTasks(
            "report",
            f"{goal}\nStatus: {status}\nTesting: {'passed' if testingResult.get('passed') else 'failed'}",
            conversationMessages,
        )
        await taskRunner.reportTasksGenerated(taskId, "report", tasks)

        allNewMessages = []
        finalContent = ""

        for i, task in enumerate(tasks):
            await taskRunner.reportTaskStarted(taskId, "report", i)
            startTime = time.time()

            inputMessages = [
                SystemMessage(content=reportSystemPrompt(proceduralText, threadContext)),
                *conversationMessages,
                HumanMessage(content=(
                    f"Goal: {goal}\n"
                    f"Plan: {plan.get('goal', goal)}\n"
                    f"Implementation: {implementationResult.get('output', 'N/A')[:300]}\n"
                    f"Testing: {'PASSED' if testingResult.get('passed') else 'FAILED'}\n\n"
                    f"Report task: {task['description']}"
                )),
            ]

            result = await _reactAgent.ainvoke(
                {"messages": inputMessages},
                {"recursion_limit": 10},
            )
            newMsgs = result["messages"][len(inputMessages):]
            allNewMessages.extend(newMsgs)

            taskResult = extractLastAIContent(newMsgs)
            if taskResult:
                finalContent = taskResult

            if not finalContent:
                for msg in newMsgs:
                    if getattr(msg, "type", None) == "tool" and msg.content:
                        finalContent = msg.content
                        break

            durationMs = int((time.time() - startTime) * 1000)
            await taskRunner.reportTaskCompleted(taskId, "report", i, taskResult, durationMs)

        await agentMemory.writeProcedural(
            agentType="report", userId=userId, taskId=taskId,
            content=f"Wrote report for: {goal} (status: {status})",
            metadata={"goal": goal, "status": status},
        )

        return {
            "agentOutputs": {"report": {"content": finalContent, "status": status}},
            "status": status,
            "currentAgent": "report",
            "messages": allNewMessages,
        }
    except Exception as e:
        logger.error(f"reportNode failed taskId={taskId}: {type(e).__name__}: {e}")
        return {"errorMessage": f"{type(e).__name__}: {e}" or "Unknown error", "status": "failed"}
