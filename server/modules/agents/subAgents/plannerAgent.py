from __future__ import annotations

import json

from langchain_core.messages import HumanMessage, SystemMessage

from config.logger import logger
from modules.agents.deepMoryLLM import deepMoryLLM
from modules.agents.memory.agentMemory import agentMemory
from modules.agents.orchestrator.taskState import TaskState
from modules.agents.subAgents.tools import PLANNER_TOOLS


async def plannerNode(state: TaskState) -> dict:
    """Planner Agent: converts research findings into a structured execution plan."""
    taskId = state["taskId"]
    userId = state["userId"]
    goal = state["goal"]
    findings = state.get("researchFindings", [])
    try:
        procedural = await agentMemory.recallProcedural("planner", goal, limit=3)
        proceduralText = "\n".join(f"- {m.get('content', '')}" for m in procedural) or "None"

        findingsText = "\n".join(
            f"- {f.get('content', '')}" for f in findings
        ) or "No research findings available."

        messages = [
            SystemMessage(content=(
                "You are a Planner Agent. Create a detailed, actionable plan to achieve the goal "
                "based on the research findings. Break the work into clear sequential steps. "
                "Use createPlan tool to produce a structured plan.\n\n"
                f"Successful planning patterns from past tasks:\n{proceduralText}"
            )),
            HumanMessage(content=(
                f"Goal: {goal}\n\nResearch findings:\n{findingsText}\n\n"
                "Create a detailed plan using the createPlan tool."
            )),
        ] + list(state.get("messages", []))

        llm = deepMoryLLM.bind_tools(PLANNER_TOOLS)
        response = await llm.ainvoke(messages)

        plan = {"goal": goal, "steps": [], "rawResponse": response.content}
        if hasattr(response, "tool_calls") and response.tool_calls:
            for tc in response.tool_calls:
                if tc.get("name") == "createPlan":
                    plan = tc.get("args", plan)

        await agentMemory.writeProcedural(
            agentType="planner", userId=userId, taskId=taskId,
            content=f"Plan for: {goal}. Steps: {len(plan.get('steps', []))}",
            metadata={"goal": goal},
        )

        newMessages = list(state.get("messages", [])) + [response]
        return {"plan": plan, "currentAgent": "planner", "messages": newMessages}
    except Exception as e:
        logger.error(f"plannerNode failed taskId={taskId}: {e}")
        return {"errorMessage": str(e), "status": "failed"}
