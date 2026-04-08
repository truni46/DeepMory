from __future__ import annotations

import time

from langchain_core.messages import HumanMessage, SystemMessage
from langchain.agents import create_agent

from config.logger import logger
from modules.agents.deepMoryLLM import deepMoryLLM
from modules.agents.memory.agentMemory import agentMemory
from modules.agents.subAgents.agentUtils import extractLastAIContent, extractConversationContext
from modules.agents.subAgents.taskRunner import taskRunner
from modules.agents.subAgents.tools import RESEARCH_TOOLS

_reactAgent = create_agent(deepMoryLLM, RESEARCH_TOOLS)


async def researchNode(state: dict) -> dict:
    """Research Agent: dynamically generates research tasks, then executes each."""
    taskId = state["taskId"]
    userId = state["userId"]
    goal = state["goal"]
    try:
        episodic = await agentMemory.recallEpisodic("research", userId, limit=3)
        semantic = await agentMemory.recallSemantic(userId, goal, limit=3)

        episodicText = "\n".join(f"- {m.get('content', '')}" for m in episodic) or "None"
        semanticText = "\n".join(f"- {m.get('content', '')}" for m in semantic) or "None"

        threadContext = state.get("threadContext") or ""
        conversationMessages = extractConversationContext(state.get("messages", []))

        tasks = await taskRunner.generateTasks("research", goal, conversationMessages)
        await taskRunner.reportTasksGenerated(taskId, "research", tasks)

        allFindings = []
        allNewMessages = []

        for i, task in enumerate(tasks):
            await taskRunner.reportTaskStarted(taskId, "research", i)
            startTime = time.time()

            inputMessages = [
                SystemMessage(content=(
                    "You are a Research Agent. Use available tools to search the web and "
                    "internal knowledge base. Synthesize findings into clear, structured points.\n\n"
                    f"Past research experience:\n{episodicText}\n\n"
                    f"Relevant knowledge:\n{semanticText}"
                    + (f"\n\nThread context:\n{threadContext}" if threadContext else "")
                )),
                *conversationMessages,
                HumanMessage(content=f"Execute this research task: {task['description']}"),
            ]

            result = await _reactAgent.ainvoke(
                {"messages": inputMessages},
                {"recursion_limit": 10},
            )
            newMsgs = result["messages"][len(inputMessages):]
            allNewMessages.extend(newMsgs)

            taskResult = extractLastAIContent(newMsgs)
            allFindings.append({"source": "research", "content": taskResult, "task": task["description"]})

            durationMs = int((time.time() - startTime) * 1000)
            await taskRunner.reportTaskCompleted(taskId, "research", i, taskResult, durationMs)

        await agentMemory.writeEpisodic(
            agentType="research", userId=userId, taskId=taskId,
            content=f"Researched: {goal}. Completed {len(tasks)} tasks.",
        )
        combinedContent = "\n".join(f.get("content", "") for f in allFindings)
        if combinedContent:
            await agentMemory.writeSemantic(
                userId=userId, agentType="research", taskId=taskId,
                content=combinedContent[:500],
                metadata={"goal": goal},
            )

        return {
            "agentOutputs": {"research": {"findings": allFindings}},
            "currentAgent": "research",
            "messages": allNewMessages,
        }
    except Exception as e:
        logger.error(f"researchNode failed taskId={taskId}: {type(e).__name__}: {e}")
        return {"errorMessage": f"{type(e).__name__}: {e}" or "Unknown error", "status": "failed"}
