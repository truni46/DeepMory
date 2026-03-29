from __future__ import annotations

from langchain_core.messages import HumanMessage, SystemMessage

from config.logger import logger
from modules.agents.deepMoryLLM import deepMoryLLM
from modules.agents.memory.agentMemory import agentMemory
from modules.agents.orchestrator.taskState import TaskState
from modules.agents.subAgents.tools import TESTING_TOOLS


async def testingNode(state: TaskState) -> dict:
    """Testing Agent: validates implementation, runs tests, generates and runs test cases."""
    taskId = state["taskId"]
    userId = state["userId"]
    goal = state["goal"]
    implementation = state.get("implementationResult") or {}
    try:
        episodic = await agentMemory.recallEpisodic("testing", userId, limit=3)
        episodicText = "\n".join(f"- {m.get('content', '')}" for m in episodic) or "None"

        messages = [
            SystemMessage(content=(
                "You are a Testing Agent. Validate the implementation against the goal. "
                "Use testCaseGenerator to create tests, testRunner to run them, "
                "validator to check outputs, and invokeBrowserAgent for UI/web testing.\n\n"
                f"Common failure patterns to watch for:\n{episodicText}"
            )),
            HumanMessage(content=(
                f"Goal: {goal}\n\nImplementation result:\n{implementation.get('output', 'No output')}\n\n"
                "Run tests and validate the implementation."
            )),
        ] + list(state.get("messages", []))

        llm = deepMoryLLM.bind_tools(TESTING_TOOLS)
        response = await llm.ainvoke(messages)

        passed = "fail" not in response.content.lower() and "error" not in response.content.lower()
        testingResult = {
            "output": response.content,
            "passed": passed,
            "toolCalls": [tc.get("name") for tc in (response.tool_calls if hasattr(response, "tool_calls") and response.tool_calls else [])],
        }

        await agentMemory.writeEpisodic(
            agentType="testing", userId=userId, taskId=taskId,
            content=f"Testing {'passed' if passed else 'failed'} for: {goal}",
            metadata={"passed": passed, "goal": goal},
        )

        newMessages = list(state.get("messages", [])) + [response]
        return {"testingResult": testingResult, "currentAgent": "testing", "messages": newMessages}
    except Exception as e:
        logger.error(f"testingNode failed taskId={taskId}: {e}")
        return {"errorMessage": str(e), "status": "failed"}
