from __future__ import annotations

from langchain_core.messages import HumanMessage, SystemMessage

from config.logger import logger
from modules.agents.deepMoryLLM import deepMoryLLM
from modules.agents.orchestrator.taskState import TaskState

_VALID_AGENTS = {"research", "planner", "implement", "testing", "report", "END"}

_SYSTEM_PROMPT = """You are the Supervisor of a multi-agent pipeline. Your only job is to decide which agent to run next.

Agents available:
- research: gather information, search web and knowledge base
- planner: create a structured execution plan from research
- implement: execute the plan, write code or documents
- testing: validate and test the implementation
- report: synthesize everything into a final report
- END: the task is complete, stop

Routing rules (use judgment, these are guidelines):
1. No research yet → research
2. Has research but no plan → planner
3. Has plan but no implementation → implement
4. Has implementation but no testing → testing
5. Testing passed → report
6. Testing failed AND iterationCount < maxIterations → implement (retry)
7. Testing failed AND iterationCount >= maxIterations → report (partial failure)
8. Has final report → END
9. status is failed/cancelled → END

Respond with EXACTLY one word: the agent name or END. Nothing else."""


async def supervisorNode(state: TaskState) -> dict:
    """Supervisor node: decides which agent to run next based on current TaskState."""
    taskId = state.get("taskId", "unknown")
    try:
        if state.get("status") in ("failed", "cancelled", "completed"):
            return {"nextAgent": "END", "currentAgent": "supervisor"}

        outputs = state.get("agentOutputs", {})
        testingResult = outputs.get("testing", {}).get("result") or {}
        threadContext = state.get("threadContext") or ""

        stateContext = (
            f"Goal: {state.get('goal', '')}\n"
            f"Research findings: {'yes' if outputs.get('research') else 'no'}\n"
            f"Plan: {'yes' if outputs.get('planner') else 'no'}\n"
            f"Implementation: {'yes' if outputs.get('implement') else 'no'}\n"
            f"Testing: {'passed' if testingResult.get('passed') else ('failed' if outputs.get('testing') else 'not run')}\n"
            f"Final report: {'yes' if outputs.get('report') else 'no'}\n"
            f"Iteration: {state.get('iterationCount', 0)}/{state.get('maxIterations', 10)}\n"
            f"Status: {state.get('status', 'running')}\n"
            f"Error: {state.get('errorMessage') or 'none'}"
            + (f"\nPrevious thread work: {threadContext[:200]}" if threadContext else "")
        )

        messages = [
            SystemMessage(content=_SYSTEM_PROMPT),
            HumanMessage(content=f"Current pipeline state:\n{stateContext}\n\nWhich agent should run next?"),
        ]

        response = await deepMoryLLM.ainvoke(messages)
        nextAgent = response.content.strip().lower().rstrip(".")

        if nextAgent not in _VALID_AGENTS:
            nextAgent = "END"

        return {"nextAgent": nextAgent, "currentAgent": "supervisor"}
    except Exception as e:
        logger.error(f"supervisorNode failed taskId={taskId}: {e}")
        return {"nextAgent": "END", "currentAgent": "supervisor", "status": "failed", "errorMessage": str(e)}
