from __future__ import annotations

import time

from langchain_core.messages import HumanMessage, SystemMessage
from langchain.agents import create_agent

from config.logger import logger
from modules.agents.deepMoryLLM import deepMoryLLM
from modules.agents.memory.agentMemory import agentMemory
from modules.agents.subAgents.agentUtils import extractConversationContext
from modules.agents.subAgents.taskRunner import taskRunner
from modules.agents.subAgents.tools import PLANNER_TOOLS
from common.prompts import plannerSystemPrompt

_reactAgent = create_agent(deepMoryLLM, PLANNER_TOOLS)


async def plannerNode(state: dict) -> dict:
    """Planner Agent: dynamically generates planning tasks, then executes each."""
    taskId = state["taskId"]
    userId = state["userId"]
    goal = state["goal"]
    findings = state.get("agentOutputs", {}).get("research", {}).get("findings", [])
    try:
        procedural = await agentMemory.recallProcedural("planner", goal, limit=3)
        proceduralText = "\n".join(f"- {m.get('content', '')}" for m in procedural) or "None"

        findingsText = "\n".join(
            f"- {f.get('content', '')}" for f in findings
        ) or "No research findings available."

        threadContext = state.get("threadContext") or ""
        conversationMessages = extractConversationContext(state.get("messages", []))

        tasks = await taskRunner.generateTasks("planner", goal, conversationMessages)
        await taskRunner.reportTasksGenerated(taskId, "planner", tasks)

        plan = {"goal": goal, "steps": []}
        allNewMessages = []

        for i, task in enumerate(tasks):
            await taskRunner.reportTaskStarted(taskId, "planner", i)
            startTime = time.time()

            inputMessages = [
                SystemMessage(content=plannerSystemPrompt(proceduralText, threadContext)),
                *conversationMessages,
                HumanMessage(content=(
                    f"Goal: {goal}\n\nResearch findings:\n{findingsText}\n\n"
                    f"Planning task: {task['description']}"
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
                    for tc in msg.tool_calls:
                        if tc.get("name") == "createPlan":
                            args = tc.get("args", {})
                            steps = args.get("steps", [])
                            plan = {
                                "goal": args.get("goal", goal),
                                "steps": [
                                    {"index": j + 1, "description": s, "status": "pending"}
                                    for j, s in enumerate(steps)
                                ],
                                "notes": args.get("notes", ""),
                            }

            taskResult = ""
            for msg in reversed(newMsgs):
                if getattr(msg, "type", None) == "ai" and msg.content:
                    taskResult = msg.content
                    break

            durationMs = int((time.time() - startTime) * 1000)
            await taskRunner.reportTaskCompleted(taskId, "planner", i, taskResult, durationMs)

        if not plan.get("steps") and allNewMessages:
            for msg in reversed(allNewMessages):
                if getattr(msg, "type", None) == "ai" and msg.content:
                    plan["rawResponse"] = msg.content
                    break

        await agentMemory.writeProcedural(
            agentType="planner", userId=userId, taskId=taskId,
            content=f"Plan for: {goal}. Steps: {len(plan.get('steps', []))}",
            metadata={"goal": goal},
        )

        return {"agentOutputs": {"planner": {"plan": plan}}, "currentAgent": "planner", "messages": allNewMessages}
    except Exception as e:
        logger.error(f"plannerNode failed taskId={taskId}: {type(e).__name__}: {e}")
        return {"errorMessage": f"{type(e).__name__}: {e}" or "Unknown error", "status": "failed"}
