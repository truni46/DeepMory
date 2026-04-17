from __future__ import annotations

import os
import subprocess
import uuid
from pathlib import Path
from typing import Optional

from langchain_core.tools import tool
from tavily import TavilyClient

from config.logger import logger
from modules.rag.ragService import ragService

_WORKSPACE = Path(os.getenv("AGENT_WORKSPACE_DIR", "./agent_workspace")).resolve()
_SHELL_TIMEOUT = int(os.getenv("AGENT_SHELL_TIMEOUT", "30"))
_ALLOWED_COMMANDS = {"python", "pytest", "npm", "pip"}
_TAVILY_KEY = os.getenv("TAVILY_API_KEY", "")


def _getTavily() -> TavilyClient:
    return TavilyClient(api_key=_TAVILY_KEY)


def _ensureWorkspace() -> None:
    _WORKSPACE.mkdir(parents=True, exist_ok=True)


def _checkAllowedCommand(command: str) -> bool:
    firstWord = command.strip().split()[0] if command.strip() else ""
    return firstWord in _ALLOWED_COMMANDS


# Research Agent tools

@tool
async def webSearch(query: str) -> str:
    """Search the web for information using Tavily. Returns a summary of search results."""
    try:
        if not _TAVILY_KEY:
            return "webSearch: TAVILY_API_KEY not configured."
        client = _getTavily()
        results = client.search(query=query, max_results=5)
        items = results.get("results", [])
        if not items:
            return f"No results found for: {query}"
        lines = [f"- [{r.get('title', '')}]: {r.get('content', '')}" for r in items]
        return "\n".join(lines)
    except Exception as e:
        logger.error(f"webSearch failed query={query}: {e}")
        return f"webSearch error: {e}"


@tool
async def ragSearch(query: str, projectId: Optional[str] = None, userId: Optional[str] = None) -> str:
    """Search internal knowledge base using RAG. Provide projectId for project-scoped search or userId for user-scoped."""
    try:
        if projectId:
            results = await ragService.searchContext(query, projectId)
        elif userId:
            results = await ragService.searchMemoryVectors(userId, query)
        else:
            return "ragSearch: provide projectId or userId."
        if not results:
            return "No relevant documents found."
        if isinstance(results, list):
            return "\n\n".join(str(r) for r in results[:5])
        return str(results)
    except Exception as e:
        logger.error(f"ragSearch failed query={query}: {e}")
        return f"ragSearch error: {e}"


@tool
async def documentReader(documentId: str) -> str:
    """Read the content of a document by its ID from the knowledge base."""
    try:
        from config.database import db
        if db.useDatabase and db.pool:
            async with db.pool.acquire() as conn:
                row = await conn.fetchrow(
                    'SELECT "content", "title" FROM documents WHERE "id"=$1',
                    documentId,
                )
                if row:
                    return f"# {row['title']}\n\n{row['content']}"
        return f"documentReader: document {documentId} not found."
    except Exception as e:
        logger.error(f"documentReader failed documentId={documentId}: {e}")
        return f"documentReader error: {e}"


# Planner Agent tools

@tool
def createPlan(goal: str, steps: list[str], notes: Optional[str] = None) -> dict:
    """Create a structured plan with ordered steps. Returns a plan dict."""
    try:
        return {
            "planId": str(uuid.uuid4()),
            "goal": goal,
            "steps": [{"index": i + 1, "description": s, "status": "pending"} for i, s in enumerate(steps)],
            "notes": notes or "",
        }
    except Exception as e:
        logger.error(f"createPlan failed goal={goal}: {e}")
        return {"error": str(e)}


@tool
def validatePlan(plan: dict) -> dict:
    """Validate a plan dict for completeness. Returns validation result."""
    try:
        issues = []
        if not plan.get("goal"):
            issues.append("Missing goal")
        steps = plan.get("steps", [])
        if not steps:
            issues.append("No steps defined")
        if len(steps) > 20:
            issues.append("Too many steps (max 20)")
        return {"valid": len(issues) == 0, "issues": issues, "stepCount": len(steps)}
    except Exception as e:
        logger.error(f"validatePlan failed: {e}")
        return {"valid": False, "issues": [str(e)]}


# Implement Agent tools

@tool
def codeWriter(filename: str, content: str) -> str:
    """Write code content to a file in the agent workspace. Returns the file path."""
    try:
        _ensureWorkspace()
        filePath = _WORKSPACE / filename
        filePath.parent.mkdir(parents=True, exist_ok=True)
        filePath.write_text(content, encoding="utf-8")
        return f"Written: {filePath}"
    except Exception as e:
        logger.error(f"codeWriter failed filename={filename}: {e}")
        return f"codeWriter error: {e}"


@tool
def fileWriter(filename: str, content: str) -> str:
    """Write text/markdown content to a file in the agent workspace."""
    try:
        _ensureWorkspace()
        filePath = _WORKSPACE / filename
        filePath.parent.mkdir(parents=True, exist_ok=True)
        filePath.write_text(content, encoding="utf-8")
        return f"Written: {filePath}"
    except Exception as e:
        logger.error(f"fileWriter failed filename={filename}: {e}")
        return f"fileWriter error: {e}"


@tool
def shellRunner(command: str) -> str:
    """Run a sandboxed shell command in the agent workspace. Only python/pytest/npm/pip allowed."""
    try:
        if not _checkAllowedCommand(command):
            return f"shellRunner: command '{command.split()[0]}' not in allowlist {_ALLOWED_COMMANDS}"
        _ensureWorkspace()
        result = subprocess.run(
            command,
            shell=True,
            cwd=str(_WORKSPACE),
            capture_output=True,
            text=True,
            timeout=_SHELL_TIMEOUT,
        )
        output = result.stdout + result.stderr
        return output[:4000] if len(output) > 4000 else output
    except subprocess.TimeoutExpired:
        logger.error(f"shellRunner timeout command={command}")
        return f"shellRunner: command timed out after {_SHELL_TIMEOUT}s"
    except Exception as e:
        logger.error(f"shellRunner failed command={command}: {e}")
        return f"shellRunner error: {e}"


# Testing Agent tools

@tool
def testCaseGenerator(goal: str, implementation: str) -> str:
    """Generate test case stubs based on a goal and implementation description. Returns pytest code."""
    try:
        testCode = f"""# Auto-generated test cases for: {goal}
import pytest


def test_basic():
    # TODO: implement test for core functionality
    pass


def test_edge_cases():
    # TODO: implement edge case tests
    pass


def test_error_handling():
    # TODO: implement error scenario tests
    pass
"""
        testFile = f"test_{uuid.uuid4().hex[:8]}.py"
        _ensureWorkspace()
        (_WORKSPACE / testFile).write_text(testCode, encoding="utf-8")
        return f"Test file created: {testFile}\n\n{testCode}"
    except Exception as e:
        logger.error(f"testCaseGenerator failed goal={goal}: {e}")
        return f"testCaseGenerator error: {e}"


@tool
def codeRunner(filename: str) -> str:
    """Run a Python file in the agent workspace and return its output."""
    try:
        _ensureWorkspace()
        result = subprocess.run(
            ["python", filename],
            cwd=str(_WORKSPACE),
            capture_output=True,
            text=True,
            timeout=_SHELL_TIMEOUT,
        )
        output = result.stdout + result.stderr
        return output[:4000] if len(output) > 4000 else output
    except subprocess.TimeoutExpired:
        return f"codeRunner: timed out after {_SHELL_TIMEOUT}s"
    except Exception as e:
        logger.error(f"codeRunner failed filename={filename}: {e}")
        return f"codeRunner error: {e}"


@tool
def testRunner(pattern: str = "test_*.py") -> str:
    """Run pytest in the agent workspace matching the given file pattern."""
    try:
        _ensureWorkspace()
        result = subprocess.run(
            ["pytest", pattern, "-v", "--tb=short"],
            cwd=str(_WORKSPACE),
            capture_output=True,
            text=True,
            timeout=_SHELL_TIMEOUT * 2,
        )
        output = result.stdout + result.stderr
        return output[:4000] if len(output) > 4000 else output
    except subprocess.TimeoutExpired:
        return f"testRunner: timed out"
    except Exception as e:
        logger.error(f"testRunner failed pattern={pattern}: {e}")
        return f"testRunner error: {e}"


@tool
def validator(content: str, criteria: list[str]) -> dict:
    """Validate content against a list of criteria. Returns pass/fail per criterion."""
    try:
        results = []
        for criterion in criteria:
            passed = criterion.lower() in content.lower()
            results.append({"criterion": criterion, "passed": passed})
        passCount = sum(1 for r in results if r["passed"])
        return {
            "passed": passCount == len(criteria),
            "passCount": passCount,
            "total": len(criteria),
            "details": results,
        }
    except Exception as e:
        logger.error(f"validator failed: {e}")
        return {"passed": False, "error": str(e)}


@tool
async def invokeBrowserAgent(task: str, url: Optional[str] = None) -> str:
    """Invoke the BrowserAgent sub-graph to perform a browser automation task."""
    try:
        from modules.agents.subAgents.browserAgent import browserAgent
        result = await browserAgent.run(task=task, url=url)
        return result
    except Exception as e:
        logger.error(f"invokeBrowserAgent failed task={task}: {e}")
        return f"invokeBrowserAgent error: {e}"


# Report Agent tools

@tool
def reportWriter(
    title: str,
    summary: str,
    sections: list[dict],
    status: str = "completed",
) -> str:
    """Write a structured markdown report. sections: list of {heading, content} dicts."""
    try:
        lines = [f"# {title}", "", f"**Status:** {status}", "", "## Summary", "", summary, ""]
        for section in sections:
            lines.append(f"## {section.get('heading', 'Section')}")
            lines.append("")
            lines.append(section.get("content", ""))
            lines.append("")
        report = "\n".join(lines)
        reportFile = f"report_{uuid.uuid4().hex[:8]}.md"
        _ensureWorkspace()
        (_WORKSPACE / reportFile).write_text(report, encoding="utf-8")
        return report
    except Exception as e:
        logger.error(f"reportWriter failed title={title}: {e}")
        return f"reportWriter error: {e}"


@tool
def summaryGenerator(content: str, maxWords: int = 150) -> str:
    """Generate a concise summary from content, truncated to maxWords."""
    try:
        words = content.split()
        if len(words) <= maxWords:
            return content
        return " ".join(words[:maxWords]) + "..."
    except Exception as e:
        logger.error(f"summaryGenerator failed: {e}")
        return f"summaryGenerator error: {e}"


# Tool registries per agent

RESEARCH_TOOLS = [webSearch, ragSearch, documentReader]
PLANNER_TOOLS = [createPlan, validatePlan]
IMPLEMENT_TOOLS = [codeWriter, fileWriter, shellRunner]
TESTING_TOOLS = [codeRunner, testRunner, validator, testCaseGenerator, invokeBrowserAgent]
REPORT_TOOLS = [reportWriter, summaryGenerator]
