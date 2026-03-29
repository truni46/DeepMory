# Multi-Agent System Design — DeepMory

**Date:** 2026-03-29
**Project:** DeepMory (Internal AI Platform)
**Scope:** R&D Department — Phase 1

---

## Overview

A multi-agent system built on LangGraph integrated into the existing FastAPI backend. Five specialized agents (Research, Planner, Implement, Testing, Report) are orchestrated by a Supervisor using the LangGraph Supervisor Pattern. The system supports dynamic orchestration, hybrid memory (short-term conversation memory + long-term episodic/semantic/procedural memory), and dual activation via chat or explicit slash commands.

---

## Requirements

### Functional
- Orchestrator (Supervisor) dynamically routes between 5 specialized agents based on TaskState
- User can activate pipeline via natural chat or explicit `/agent` commands
- Agents maintain short-term conversation memory within a task session
- Each agent builds and recalls long-term memory across tasks (episodic, semantic, procedural)
- Real-time task output streamed to frontend via SSE

### Non-Functional
- Integrated into existing FastAPI server (no separate microservice)
- Reuses existing LLM provider, PostgreSQL, Redis, Qdrant infrastructure
- Agent memory is isolated from chatbot memory (chatbot memory handled separately later)
- Maximum `maxIterations` guard to prevent infinite loops

---

## Architecture

### Module Structure

```
server/modules/agents/
├── router.py                  # FastAPI endpoints
├── service.py                 # AgentFacade — single entry point
├── repository.py              # Task + memory persistence (PostgreSQL)
│
├── orchestrator/
│   ├── supervisorAgent.py     # LangGraph Supervisor LLM node
│   ├── taskState.py           # Shared TaskState schema (TypedDict)
│   └── graphBuilder.py        # Builds and compiles LangGraph StateGraph
│
├── subAgents/
│   ├── researchAgent.py
│   ├── plannerAgent.py
│   ├── implementAgent.py
│   ├── testingAgent.py
│   └── reportAgent.py
│
├── memory/
│   ├── taskMemory.py          # Short-term: Redis conversation memory
│   └── agentMemory.py         # Long-term: episodic + semantic + procedural
│
└── llm/
    └── deepMoryLLM.py         # LangChain BaseChatModel adapter wrapping llmProvider
```

### Integration with Existing Codebase

| Existing Component | Usage in Agents |
|---|---|
| `llm/llmProvider.py` | Wrapped by `deepMoryLLM.py` adapter into LangChain `BaseChatModel` |
| `memory/service.py` | Reference only — agent memory is independent |
| `rag/ragService.py` | Research Agent calls directly for vector search |
| Redis | `taskMemory.py` stores conversation history per task (TTL 24h) |
| PostgreSQL | `repository.py` persists tasks, agent runs, long-term memories |
| Qdrant | Semantic and procedural memory vector storage |
| `message/router.py` | Detects `/agent` prefix → routes to `agentService` |

---

## Agent Definitions

### Supervisor Agent

The Supervisor is a LangGraph LLM node given a single tool: `routeToAgent(agentName)`. On each invocation it receives the full `TaskState` and decides which agent to call next (or `END`).

Routing logic (LLM-driven, not hardcoded):
- No research → `research`
- Research done, no plan → `planner`
- Plan done, no implementation → `implement`
- Implementation done, no testing → `testing`
- Testing passed → `report`
- Testing failed + `iterationCount < maxIterations` → `implement`
- Testing failed + `iterationCount >= maxIterations` → `report` (partial failure)
- Report done → `END`

The LLM Supervisor can deviate from this default flow when context warrants it (e.g., insufficient research confidence → re-research before planning).

### Sub-Agents

| Agent | Responsibility | Tools | Long-term Memory Written |
|---|---|---|---|
| **Research** | Search web, internal docs, knowledge base | `webSearch`, `ragSearch`, `documentReader` | Findings by domain/topic (semantic) |
| **Planner** | Analyze research → produce detailed step plan | `createPlan`, `validatePlan` | Successful plan patterns (procedural) |
| **Implement** | Execute plan: write code, draft documents | `codeWriter`, `fileWriter`, `shellRunner` | Team tech stack preferences (procedural) |
| **Testing** | Validate implementation: run tests, review | `codeRunner`, `testRunner`, `validator` | Common failure patterns (episodic) |
| **Report** | Synthesize full task → final report | `reportWriter`, `summaryGenerator` | Report format preferences (procedural) |

---

## TaskState Schema

Shared state passed between all nodes in the LangGraph graph:

```python
class TaskState(TypedDict):
    # Identity
    taskId: str
    userId: str
    goal: str

    # Flow control
    currentAgent: str
    nextAgent: str | None
    iterationCount: int
    maxIterations: int                        # default: 10
    status: Literal["running", "completed", "failed", "partial_failure", "cancelled", "waiting_human"]
    errorMessage: str | None

    # Conversation memory (short-term)
    messages: list[BaseMessage]               # Full conversation history for this task

    # Agent outputs (accumulated)
    researchFindings: list[dict]
    plan: dict | None
    implementationResult: dict | None
    testingResult: dict | None
    finalReport: str | None
```

---

## Memory Architecture

### Short-term Memory — Conversation Memory

Stores the full message thread of the current task session. Enables the agent to resolve references like "choose A" by looking back at what option A was.

```
Redis key:  agent:task:{taskId}:messages
Value:      list[BaseMessage] serialized as JSON
TTL:        24 hours
```

Every LLM call within the task receives the full message history as context. This is the LangGraph `messages` state field, persisted to Redis via a custom checkpointer.

### Long-term Memory — Three Types

All three types are stored in `agentMemories` table (PostgreSQL) with vector embeddings in Qdrant where applicable.

#### 1. Episodic Memory — "What I did before"

Records of past task runs: what the input was, what the agent did, the outcome.

- Storage: PostgreSQL
- Query: filter by `agentType`, `userId`, date range
- Example: Research Agent recalls "last time I researched vector DBs, arxiv + official docs gave the best results"

#### 2. Semantic Memory — "What I know"

Facts, findings, and knowledge stored as vector embeddings for similarity-based recall.

- Storage: Qdrant (vectors) + PostgreSQL (metadata)
- Query: similarity search by current task goal/topic
- Example: "LangGraph is well-suited for stateful multi-agent systems" recalled when planning orchestration

#### 3. Procedural Memory — "How I do things"

Effective workflows, strategies, and patterns that have proven successful.

- Storage: PostgreSQL + Qdrant
- Query: filter by `agentType` + similarity search by task context
- Example: Planner recalls "for this team, 3-phase plans outperform 2-phase plans"; Testing recalls "this project uses pytest + async"

### PostgreSQL Schema — `agentMemories`

```sql
"id"          UUID PRIMARY KEY
"agentType"   VARCHAR    -- 'research' | 'planner' | 'implement' | 'testing' | 'report'
"userId"      UUID
"taskId"      UUID
"memoryType"  VARCHAR    -- 'episodic' | 'semantic' | 'procedural'
"content"     TEXT
"metadata"    JSONB      -- { topic, tags, confidence, outcome, successRate, ... }
"vectorId"    VARCHAR    -- Qdrant point ID (nullable, for semantic/procedural)
"createdAt"   TIMESTAMP
```

### Memory Lifecycle Per Agent Run

```
Agent node starts
    │
    ├─ 1. Load short-term: conversation history from Redis
    ├─ 2. Recall long-term:
    │      ├─ Episodic:    recent task runs for this agentType + userId
    │      ├─ Semantic:    similarity search against current goal
    │      └─ Procedural:  patterns for this agentType + context
    │
    ├─ 3. LLM call with full context (messages + recalled memories)
    │
    └─ 4. After completion, write to long-term:
           ├─ Episodic:    record this run (input, output, outcome)
           ├─ Semantic:    store new findings/knowledge discovered
           └─ Procedural:  update pattern if a new effective strategy was used
```

---

## LLM Adapter

`deepMoryLLM.py` wraps the existing `llmProvider` into a LangChain `BaseChatModel` so LangGraph can use it without modifying the provider layer.

```
LangGraph Agent
      │ ainvoke()
      ▼
DeepMoryLLM (BaseChatModel adapter)
      │ generateResponse()
      ▼
llmProvider.py (unchanged)
      │
      ▼
Gemini / Ollama / OpenAI / vLLM
```

---

## API Endpoints

```
POST   /api/v1/agents/tasks                  # Create new task (explicit)
GET    /api/v1/agents/tasks                  # List user's tasks
GET    /api/v1/agents/tasks/{taskId}         # Task detail + current status
DELETE /api/v1/agents/tasks/{taskId}         # Cancel running task

GET    /api/v1/agents/tasks/{taskId}/stream  # SSE: real-time agent output
GET    /api/v1/agents/memories               # View user's long-term memories
DELETE /api/v1/agents/memories/{memoryId}    # Delete specific memory
```

### Slash Command Activation

Handled in `message/router.py` — detect `/` prefix and route to `agentService.runFromCommand()`:

```
/research <query>     → Research Agent only
/plan <goal>          → Research + Planner
/implement <planId>   → Implement Agent with existing plan
/report <taskId>      → Report Agent for completed task
/run <goal>           → Full pipeline (all agents)
```

---

## Error Handling

| Scenario | Handling |
|---|---|
| Agent LLM call fails | Retry up to 3× with exponential backoff; on final failure write error to TaskState |
| Testing fails repeatedly | Supervisor routes to Report with `status: partial_failure` after `maxIterations` |
| Redis unavailable | Fallback to in-process state store; log warning |
| Task cancelled by user | Call LangGraph `acancel()`, set status `cancelled` in DB |
| Unhandled exception in agent | Caught at `AgentFacade`, full context logged, error streamed to frontend |

All `try/except` blocks log with function name and relevant IDs per project error handling rules. Background tasks never re-raise.

---

## Out of Scope (Phase 1)

- Chatbot memory (separate system, handled later)
- Human-in-the-loop interrupts within agent runs
- Agent collaboration (agents calling other agents directly)
- Multi-user task sharing
