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
- Maximum `maxIterations` guard to prevent infinite loops (configurable via `AGENT_MAX_ITERATIONS` env var, default `10`)

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
│   ├── reportAgent.py
│   └── browserAgent.py    # Sub-agent of Testing, wraps Claude in Chrome MCP
│
├── memory/
│   ├── taskMemory.py          # Short-term: Redis conversation memory + RedisCheckpointer
│   └── agentMemory.py         # Long-term: episodic + semantic + procedural
│
└── deepMoryLLM.py             # LangChain BaseChatModel adapter wrapping llmProvider
                               # Single file, not a provider registry — adapter only
```

### Integration with Existing Codebase

| Existing Component | Usage in Agents |
|---|---|
| `llm/llmProvider.py` | Wrapped by `deepMoryLLM.py` adapter into LangChain `BaseChatModel` |
| `memory/service.py` | Not used — agent memory is fully independent |
| `rag/ragService.py` | Research Agent calls `ragService.searchContext(query, projectId)` when a `projectId` is present in TaskState; falls back to `ragService.searchMemoryVectors(userId, query)` for user-scoped knowledge when no project context |
| Redis | `taskMemory.py` stores conversation history and graph checkpoint state per task (TTL 24h) |
| PostgreSQL | `repository.py` persists tasks, agent runs, long-term memories |
| Qdrant | Direct Qdrant client in `agentMemory.py` for semantic/procedural memory (separate from LightRAG-managed collections) |
| `message/router.py` | Detects `/` prefix → intercepts before `messageService` → routes to `agentService.runFromCommand()` |

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

The Supervisor LLM call is **non-streaming** (it returns a tool call, not a text response). Sub-agent LLM calls use streaming where appropriate.

### Sub-Agents

| Agent | Responsibility | Tools | Long-term Memory Written |
|---|---|---|---|
| **Research** | Search web, internal docs, knowledge base | `webSearch`, `ragSearch`, `documentReader` | Findings by domain/topic (semantic) |
| **Planner** | Analyze research → produce detailed step plan | `createPlan`, `validatePlan` | Successful plan patterns (procedural) |
| **Implement** | Execute plan: write code, draft documents | `codeWriter`, `fileWriter`, `shellRunner` | Team tech stack preferences (procedural) |
| **Testing** | Validate implementation: run tests, generate test cases, invoke BrowserAgent | `codeRunner`, `testRunner`, `validator`, `testCaseGenerator`, `invokeBrowserAgent` | Common failure patterns (episodic) |
| **Report** | Synthesize full task → final report | `reportWriter`, `summaryGenerator` | Report format preferences (procedural) |
| **BrowserAgent** | Control browser like a real user for E2E testing and web interaction | `navigate`, `click`, `fill`, `screenshot`, `assertPage`, `getPageText` | UI patterns and tested flows (episodic) |

**BrowserAgent** is a sub-agent of Testing — it is not routed by the Supervisor directly. Testing Agent invokes it via `invokeBrowserAgent(task)` tool call, which spawns a BrowserAgent subgraph. BrowserAgent can also be called independently via `/browser <task>` slash command.

BrowserAgent is built on top of the existing **Claude in Chrome MCP** (`mcp__Claude_in_Chrome__*`) tools, eliminating the need to implement Playwright from scratch.

#### BrowserAgent Module Location

```
server/modules/agents/subAgents/
└── browserAgent.py    # BrowserAgent subgraph + tool wrappers over Claude in Chrome MCP
```

#### shellRunner Safety Constraints

The `shellRunner` tool on the Implement Agent is sandboxed with the following constraints enforced at the tool implementation level:
- Executes only within a configured workspace directory (`AGENT_WORKSPACE_DIR` env var, default `./agent_workspace`)
- Command allowlist enforced: only `python`, `pytest`, `npm`, `pip` and their subcommands are permitted
- Hard timeout: `AGENT_SHELL_TIMEOUT` env var, default `30` seconds
- No network access from shell commands (file system operations only)

---

## TaskState Schema

Shared state passed between all nodes in the LangGraph graph:

```python
class TaskState(TypedDict):
    # Identity
    taskId: str
    userId: str
    conversationId: str | None    # originating chat conversation (if triggered from chat)
    projectId: str | None         # project context for ragService.searchContext()

    # Flow control
    currentAgent: str
    nextAgent: str | None
    iterationCount: int
    maxIterations: int            # default: int(os.getenv("AGENT_MAX_ITERATIONS", 10))
    status: Literal["running", "completed", "failed", "partial_failure", "cancelled"]
    errorMessage: str | None

    # Conversation memory (short-term)
    messages: list[BaseMessage]   # Full conversation history for this task

    # Agent outputs (accumulated)
    goal: str
    researchFindings: list[dict]
    plan: dict | None
    implementationResult: dict | None
    testingResult: dict | None
    finalReport: str | None
```

Note: `waiting_human` is excluded from Phase 1. Human-in-the-loop is deferred to Phase 2.

---

## Memory Architecture

### Short-term Memory — Conversation Memory

Stores the full message thread of the current task session. Enables the agent to resolve references like "choose A" by looking back at what option A was.

```
Redis key: agent:task:{taskId}:messages
Value:     list[BaseMessage] serialized as JSON
TTL:       24 hours
```

Every LLM call within the task receives the full message history as context. This is the LangGraph `messages` state field, persisted to Redis via `RedisCheckpointer`.

#### RedisCheckpointer

Located in `memory/taskMemory.py`. Implements LangGraph's `BaseCheckpointSaver` interface (`get`, `put`, `list` methods).

```
Redis key schema (checkpointer — separate from message list):
  agent:checkpoint:{taskId}:latest     → serialized LangGraph Checkpoint
  agent:checkpoint:{taskId}:{stepId}   → per-step checkpoint (for resume)
```

The message list key (`agent:task:{taskId}:messages`) is written by the Supervisor after each agent completes, and is a convenience read cache for agents. The authoritative state lives in the LangGraph checkpoint keys.

### Long-term Memory — Three Types

All three types are stored in the `agentMemories` PostgreSQL table. Semantic and procedural types additionally store vector embeddings in Qdrant via a **direct Qdrant client** in `agentMemory.py` (not through LightRAG). This keeps agent memory fully decoupled from the RAG pipeline.

#### Qdrant Collections for Agent Memory

| Collection Name | Memory Type | Scope |
|---|---|---|
| `agent_semantic_{userId}` | Semantic | Per user — findings and knowledge |
| `agent_procedural_{agentType}` | Procedural | Per agent type — effective patterns |

#### 1. Episodic Memory — "What I did before"

Records of past task runs: what the input was, what the agent did, the outcome.

- Storage: PostgreSQL only (structured, queryable by time/agent/user)
- Example: Research Agent recalls "last time I researched vector DBs, arxiv + official docs gave the best results"

#### 2. Semantic Memory — "What I know"

Facts, findings, and knowledge stored as vector embeddings for similarity-based recall.

- Storage: Qdrant collection `agent_semantic_{userId}` + PostgreSQL metadata row
- Query: similarity search by current task goal/topic
- Example: "LangGraph is well-suited for stateful multi-agent systems" recalled when planning orchestration

#### 3. Procedural Memory — "How I do things"

Effective workflows, strategies, and patterns that have proven successful.

- Storage: Qdrant collection `agent_procedural_{agentType}` + PostgreSQL metadata row
- Query: filter by `agentType` + similarity search by task context
- Example: Planner recalls "for this team, 3-phase plans outperform 2-phase plans"

### PostgreSQL Schema

**Table: `agentTasks`**
```sql
"id"           UUID PRIMARY KEY DEFAULT gen_random_uuid()
"userId"       UUID NOT NULL REFERENCES users(id)
"conversationId" UUID REFERENCES conversations(id)
"projectId"    UUID REFERENCES projects(id)
"goal"         TEXT NOT NULL
"status"       VARCHAR NOT NULL DEFAULT 'running'
"errorMessage" TEXT
"finalReport"  TEXT
"createdAt"    TIMESTAMP DEFAULT NOW()
"updatedAt"    TIMESTAMP DEFAULT NOW()
```

**Table: `agentRuns`**
```sql
"id"           UUID PRIMARY KEY DEFAULT gen_random_uuid()
"taskId"       UUID NOT NULL REFERENCES "agentTasks"(id)
"agentType"    VARCHAR NOT NULL
"iterationNum" INTEGER NOT NULL
"input"        JSONB
"output"       JSONB
"status"       VARCHAR NOT NULL
"durationMs"   INTEGER
"createdAt"    TIMESTAMP DEFAULT NOW()
```

**Table: `agentMemories`**
```sql
"id"           UUID PRIMARY KEY DEFAULT gen_random_uuid()
"agentType"    VARCHAR NOT NULL
"userId"       UUID NOT NULL REFERENCES users(id)
"taskId"       UUID REFERENCES "agentTasks"(id)
"memoryType"   VARCHAR NOT NULL   -- 'episodic' | 'semantic' | 'procedural'
"content"      TEXT NOT NULL
"metadata"     JSONB DEFAULT '{}'
"vectorId"     VARCHAR             -- Qdrant point ID (semantic + procedural only)
"createdAt"    TIMESTAMP DEFAULT NOW()
```

Migration file: `server/migrations/003_agent_system.sql`

### Memory Lifecycle Per Agent Run

```
Agent node starts
    │
    ├─ 1. Load short-term: conversation history from Redis
    ├─ 2. Recall long-term:
    │      ├─ Episodic:    recent task runs for this agentType + userId (PostgreSQL)
    │      ├─ Semantic:    similarity search against current goal (Qdrant)
    │      └─ Procedural:  patterns for this agentType + context (Qdrant)
    │
    ├─ 3. LLM call with full context (messages + recalled memories)
    │
    └─ 4. After completion, write to long-term:
           ├─ Episodic:    record this run (input, output, outcome)
           ├─ Semantic:    store new findings/knowledge discovered
           └─ Procedural:  update pattern if a new effective strategy was used
```

---

## LLM Adapter — `deepMoryLLM.py`

Wraps the existing `llmProvider` into a LangChain `BaseChatModel`. This is a single-file adapter — it is not a provider registry and no additional provider files should be added here.

### Streaming Contract

- `_agenerate()` (non-streaming): used by the Supervisor node. Accumulates the full provider response into `ChatResult` before returning.
- `_astream()` (streaming): used by sub-agent nodes. Yields `ChatGenerationChunk` objects from the provider's async generator. For providers that do not support native streaming (e.g., `GeminiNativeProvider` in non-streaming mode), the adapter falls back to `_agenerate()` and yields a single chunk.

```
LangGraph Supervisor (non-streaming)     LangGraph Sub-agent (streaming)
        │ _agenerate()                           │ _astream()
        ▼                                        ▼
DeepMoryLLM adapter                     DeepMoryLLM adapter
        │ generateResponse()                     │ streamResponse() async gen
        ▼                                        ▼
llmProvider.py (unchanged)              llmProvider.py (unchanged)
        │                                        │
        ▼                                        ▼
Gemini / Ollama / OpenAI / vLLM         Gemini / Ollama / OpenAI / vLLM
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

### Slash Command Routing

Slash commands are intercepted in `message/router.py` **before** the message is passed to `messageService`. Detection logic:

```python
# In message/router.py POST /messages handler:
if content.startswith("/"):
    task = await agentService.runFromCommand(userId, conversationId, content)
    # Return taskId immediately; client switches to SSE stream for output
    return {"taskId": task.taskId, "streaming": True}
# else: normal message flow
await messageService.processMessageFlow(...)
```

The agent task streams output via `GET /api/v1/agents/tasks/{taskId}/stream`. The final report is also posted back to the originating conversation as an assistant message (via `messageService.addAssistantMessage()`) so the result appears inline in the chat UI.

Supported slash commands:

```
/research <query>     → Research Agent only
/plan <goal>          → Research + Planner
/implement <planId>   → Implement Agent with existing plan
/report <taskId>      → Report Agent for completed task
/run <goal>           → Full pipeline (all agents)
/browser <task>       → BrowserAgent only (direct E2E interaction)
```

### SSE Stream Behavior

The stream endpoint delivers newline-delimited JSON events. Clients that disconnect and reconnect receive only new events (no replay). For Phase 1, event history is available via `GET /api/v1/agents/tasks/{taskId}` which returns all `agentRuns` for the task.

---

## Environment Variables

| Variable | Default | Description |
|---|---|---|
| `AGENT_MAX_ITERATIONS` | `10` | Maximum Supervisor routing iterations per task |
| `AGENT_WORKSPACE_DIR` | `./agent_workspace` | shellRunner working directory |
| `AGENT_SHELL_TIMEOUT` | `30` | shellRunner hard timeout in seconds |
| `TAVILY_API_KEY` | — | Tavily Search API key (required for Research Agent `webSearch` tool) |

---

## Error Handling

| Scenario | Handling |
|---|---|
| Agent LLM call fails | Retry up to 3× with exponential backoff; on final failure write error to TaskState |
| Testing fails repeatedly | Supervisor routes to Report with `status: partial_failure` after `maxIterations` |
| Redis unavailable | Fallback to in-process state store; log warning |
| Task cancelled by user | Call LangGraph `acancel()`, set status `cancelled` in DB |
| Unhandled exception in agent | Caught at `AgentFacade`, full context logged (taskId, agentType, iteration), error streamed to frontend |

All `try/except` blocks log with function name and relevant IDs per project error handling rules. Background tasks never re-raise.

---

## Out of Scope (Phase 1)

- Chatbot memory (separate system, handled later)
- Human-in-the-loop interrupts within agent runs (`waiting_human` status deferred to Phase 2)
- Agent collaboration (agents calling other agents directly)
- Multi-user task sharing
- SSE stream replay on reconnect
