# API Reference

Base URL: '/api/v1'

All endpoints require JWT authentication via 'Authorization: Bearer <token>' header, except '/auth/register' and '/auth/login'.

## Auth

| Method | Path             | Description                                             | Status |
| ------ | ---------------- | ------------------------------------------------------- | ------ |
| POST   | '/auth/register' | Register new user (email, password, username, fullName) | ✅      |
| POST   | '/auth/login'    | Login with email/password (OAuth2 form data)            | ✅      |
| GET    | '/auth/me'       | Get current user profile                                | ✅      |

## Conversations

| Method | Path                              | Description                             | Status |
| ------ | --------------------------------- | --------------------------------------- | ------ |
| GET    | '/conversations'                  | List all conversations for current user | ✅      |
| POST   | '/conversations'                  | Create new conversation                 | ✅      |
| GET    | '/conversations/{conversationId}' | Get conversation by ID                  | ✅      |
| PATCH  | '/conversations/{conversationId}' | Update conversation (title, etc.)       | ✅      |
| DELETE | '/conversations/{conversationId}' | Delete conversation                     | ✅      |

## Messages

| Method | Path                         | Description                                                                                                       | Status |
| ------ | ---------------------------- | ----------------------------------------------------------------------------------------------------------------- | ------ |
| GET    | '/messages/{conversationId}' | Get conversation message history                                                                                  | ✅      |
| POST   | '/messages/chat/completions' | Send message, receive SSE stream. Routes: slash command → agent, classified AGENT → agent task, CHAT → LLM stream | ✅      |

Slash commands (resolved in frontend before sending):

| Input                                       | Resolves To         | Agent                |
| ------------------------------------------- | ------------------- | -------------------- |
| '/agents:research' or '/research' or '/r'   | '/agents:research'  | Research Agent       |
| '/agents:plan' or '/plan' or '/p'           | '/agents:plan'      | Planning Agent       |
| '/agents:implement' or '/implement' or '/i' | '/agents:implement' | Implementation Agent |
| '/agents:report' or '/report'               | '/agents:report'    | Reporting Agent      |
| '/agents:browser' or '/browser' or '/b'     | '/agents:browser'   | Browser Agent        |

## Projects

| Method | Path                              | Description                              | Status |
| ------ | --------------------------------- | ---------------------------------------- | ------ |
| POST   | '/projects'                       | Create new project                       | ✅      |
| GET    | '/projects'                       | List user's projects                     | ✅      |
| POST   | '/projects/{projectId}/documents' | Upload document to project (file upload) | ✅      |
| GET    | '/projects/{projectId}/documents' | List documents in project                | ✅      |

## Knowledge

| Method | Path                                | Description                               | Status |
| ------ | ----------------------------------- | ----------------------------------------- | ------ |
| POST   | '/knowledge/upload'                 | Upload document file (optional projectId) | ✅      |
| GET    | '/knowledge/documents'              | List all user documents                   | ✅      |
| DELETE | '/knowledge/documents/{documentId}' | Delete document                           | ✅      |

## RAG

| Method | Path                                      | Description                                                                | Status |
| ------ | ----------------------------------------- | -------------------------------------------------------------------------- | ------ |
| POST   | '/rag/search'                             | Search knowledge base via LightRAG (query, projectId, limit, mode, rerank) | ✅      |
| POST   | '/rag/memory/search'                      | Search user's long-term memory vectors (query, limit)                      | ✅      |
| DELETE | '/rag/documents/{projectId}/{documentId}' | Delete document chunks from LightRAG                                       | ✅      |

## Memory

| Method | Path                 | Description                          | Status |
| ------ | -------------------- | ------------------------------------ | ------ |
| GET    | '/memory'            | List user memories (limit 200)       | ✅      |
| PATCH  | '/memory/{memoryId}' | Update memory content (SQL + vector) | ✅      |
| DELETE | '/memory/{memoryId}' | Delete memory (SQL + vector)         | ✅      |
| GET    | '/memory/settings'   | Get memory collection toggle state   | ✅      |
| PUT    | '/memory/settings'   | Toggle memory extraction on/off      | ✅      |

## Settings

| Method | Path        | Description               | Status |
| ------ | ----------- | ------------------------- | ------ |
| GET    | '/settings' | Get current user settings | ✅      |
| PUT    | '/settings' | Update user settings      | ✅      |

## Agents

| Method | Path                            | Description                                           | Status |
| ------ | ------------------------------- | ----------------------------------------------------- | ------ |
| POST   | '/agents/tasks'                 | Create agent task (goal, conversationId?, projectId?) | ✅      |
| GET    | '/agents/tasks'                 | List all tasks for current user                       | ✅      |
| GET    | '/agents/tasks/{taskId}'        | Get task detail + runs                                | ✅      |
| DELETE | '/agents/tasks/{taskId}'        | Cancel/delete task                                    | ✅      |
| GET    | '/agents/tasks/{taskId}/stream' | SSE stream of task execution progress                 | ⚠️      |
| GET    | '/agents/memories'              | List agent memories                                   | ✅      |
| DELETE | '/agents/memories/{memoryId}'   | Delete agent memory                                   | ✅      |

## System

| Method | Path      | Description  | Status |
| ------ | --------- | ------------ | ------ |
| GET    | '/health' | Health check | ✅      |

## SSE Streaming Endpoints

Two endpoints return Server-Sent Events:

1. **'POST /messages/chat/completions'** — chat/agent message stream
2. **'GET /agents/tasks/{taskId}/stream'** — agent task progress stream

## File Upload Endpoints

Two endpoints accept multipart file uploads:

1. **'POST /projects/{projectId}/documents'**
2. **'POST /knowledge/upload'**

## Status Legend

| Icon | Meaning                                                      |
| ---- | ------------------------------------------------------------ |
| ✅    | Endpoint returns correct HTTP response                       |
| ⚠️    | Endpoint responds but downstream processing has known issues |
| ❌    | Endpoint fails                                               |

## Known Issues (2026-04-03)

- **Agent task stream** ('GET /agents/tasks/{taskId}/stream'): endpoint returns 200 OK, but task execution pipeline has issues with Gemini thinking models requiring 'thought_signature' passthrough — fix deployed, pending verification.
- **Short-term memory**: 'compactConversation' and 'addTaskToShortTermMemory' implemented, wiring into '_runGraph' in progress.

## Stats

- **Total endpoints**: 33
- **Modules**: 10 (auth, conversations, messages, projects, knowledge, rag, memory, settings, agents, system)
