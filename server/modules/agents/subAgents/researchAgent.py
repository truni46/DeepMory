from __future__ import annotations

from langchain_core.messages import HumanMessage, SystemMessage

from config.logger import logger
from modules.agents.deepMoryLLM import deepMoryLLM
from modules.agents.memory.agentMemory import agentMemory
from modules.agents.orchestrator.taskState import TaskState
from modules.agents.subAgents.tools import RESEARCH_TOOLS


async def researchNode(state: TaskState) -> dict:
    """Research Agent: searches web and knowledge base, produces findings."""
    taskId = state["taskId"]
    userId = state["userId"]
    goal = state["goal"]
    try:
        episodic = await agentMemory.recallEpisodic("research", userId, limit=3)
        semantic = await agentMemory.recallSemantic(userId, goal, limit=3)

        episodicText = "\n".join(f"- {m.get('content', '')}" for m in episodic) or "None"
        semanticText = "\n".join(f"- {m.get('content', '')}" for m in semantic) or "None"

        messages = [
            SystemMessage(content=(
                "You are a Research Agent. Your job is to gather comprehensive information "
                "to help achieve the stated goal. Use available tools to search the web and "
                "internal knowledge base. Synthesize findings into clear, structured points.\n\n"
                f"Past research experience:\n{episodicText}\n\n"
                f"Relevant knowledge you already have:\n{semanticText}"
            )),
            HumanMessage(content=f"Research goal: {goal}"),
        ] + list(state.get("messages", []))

        llm = deepMoryLLM.bind_tools(RESEARCH_TOOLS)
        response = await llm.ainvoke(messages)
        findings = [{"source": "research", "content": response.content, "goal": goal}]

        await agentMemory.writeEpisodic(
            agentType="research", userId=userId, taskId=taskId,
            content=f"Researched: {goal}. Found {len(findings)} findings.",
        )
        if response.content:
            await agentMemory.writeSemantic(
                userId=userId, agentType="research", taskId=taskId,
                content=response.content[:500],
                metadata={"goal": goal},
            )

        newMessages = list(state.get("messages", [])) + [response]
        return {
            "researchFindings": findings,
            "currentAgent": "research",
            "messages": newMessages,
        }
    except Exception as e:
        logger.error(f"researchNode failed taskId={taskId}: {e}")
        return {"errorMessage": str(e), "status": "failed"}
