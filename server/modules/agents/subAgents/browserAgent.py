from __future__ import annotations

from typing import Optional

from config.logger import logger


class BrowserAgent:
    """BrowserAgent wraps Claude in Chrome MCP tools for browser automation."""

    async def run(self, task: str, url: Optional[str] = None) -> str:
        """Run a browser automation task. Delegates to Claude in Chrome MCP when available."""
        try:
            steps = [f"Task: {task}"]
            if url:
                steps.append(f"Starting URL: {url}")
            steps.append("BrowserAgent: Claude in Chrome MCP integration pending full wiring.")
            steps.append("Returning task description for now — full browser automation available via MCP tools.")
            return "\n".join(steps)
        except Exception as e:
            logger.error(f"BrowserAgent.run failed task={task}: {e}")
            return f"BrowserAgent error: {e}"


browserAgent = BrowserAgent()
