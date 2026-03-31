from __future__ import annotations

import time

from langchain_core.messages import HumanMessage, SystemMessage
from langchain.agents import create_agent

from config.logger import logger
from modules.agents.deepMoryLLM import deepMoryLLM
from modules.agents.memory.agentMemory import agentMemory
from modules.agents.subAgents.agentUtils import extractLastAIContent, extractConversationContext
from modules.agents.subAgents.taskRunner import taskRunner
from modules.agents.subAgents.tools import TESTING_TOOLS

_reactAgent = create_agent(deepMoryLLM, TESTING_TOOLS)


async def testingNode(state: dict) -> dict:
    """Testing Agent: dynamically generates test tasks, then executes each."""
    taskId = state["taskId"]
    userId = state["userId"]
    goal = state["goal"]
    implementation = state.get("implementationResult") or {}
    try:
        episodic = await agentMemory.recallEpisodic("testing", userId, limit=3)
        episodicText = "\n".join(f"- {m.get('content', '')}" for m in episodic) or "None"

        conversationMessages = extractConversationContext(state.get("messages", []))

        tasks = await taskRunner.generateTasks(
            "testing", f"{goal}\n\nImplementation output:\n{implementation.get('output', 'N/A')[:300]}",
            conversationMessages,
        )
        await taskRunner.reportTasksGenerated(taskId, "testing", tasks)

        allNewMessages = []
        allResults = []

        for i, task in enumerate(tasks):
            await taskRunner.reportTaskStarted(taskId, "testing", i)
            startTime = time.time()

            inputMessages = [
                SystemMessage(content=(
                    "You are a Testing Agent. Validate the implementation against the goal. "
                    "Use testCaseGenerator to create tests, testRunner to run them, "
                    "validator to check outputs.\n\n"
                    f"Common failure patterns:\n{episodicText}"
                )),
                *conversationMessages,
                HumanMessage(content=(
                    f"Goal: {goal}\nImplementation: {implementation.get('output', 'No output')[:200]}\n\n"
                    f"Testing task: {task['description']}"
                )),
            ]

            result = await _reactAgent.ainvoke({"messages": inputMessages})
            newMsgs = result["messages"][len(inputMessages):]
            allNewMessages.extend(newMsgs)

            taskResult = extractLastAIContent(newMsgs)
            allResults.append(taskResult)

            durationMs = int((time.time() - startTime) * 1000)
            await taskRunner.reportTaskCompleted(taskId, "testing", i, taskResult, durationMs)

        combinedOutput = "\n".join(allResults)
        passed = "fail" not in combinedOutput.lower() and "error" not in combinedOutput.lower()

        testingResult = {
            "output": combinedOutput,
            "passed": passed,
            "taskCount": len(tasks),
        }

        await agentMemory.writeEpisodic(
            agentType="testing", userId=userId, taskId=taskId,
            content=f"Testing {'passed' if passed else 'failed'} for: {goal}",
            metadata={"passed": passed, "goal": goal},
        )

        return {"testingResult": testingResult, "currentAgent": "testing", "messages": allNewMessages}
    except Exception as e:
        logger.error(f"testingNode failed taskId={taskId}: {e}")
        return {"errorMessage": str(e), "status": "failed"}
