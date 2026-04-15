# Token Quota Management — Design Spec

## Overview

Add token-based quota management so each user's usage is tracked and limited per session (2h rolling window) and per week. All limits are configured via environment variables. The system uses Redis for real-time tracking with PostgreSQL as the audit/rebuild source.

## Environment Variables

'''env
TOKEN_SESSION_LIMIT=500000          # Max tokens per session
TOKEN_SESSION_DURATION=7200         # Session window in seconds (2 hours)
TOKEN_WEEKLY_LIMIT=5000000          # Max tokens per week
TOKEN_WARNING_THRESHOLD=0.9         # Warning at 90% usage (0.0 - 1.0)
'''

A new config module 'server/config/quota.py' reads these env vars and exports a 'quotaConfig' singleton. Other modules import from here — never read env directly.

## Token Extraction from LLM Response

### Return format change

All providers return '(content, usageDict)' instead of just 'content'.

**usageDict format:**
'''python
{
    "promptTokens": int,
    "completionTokens": int,
    "totalTokens": int,
    "source": "api_usage" | "tiktoken_fallback"
}
'''

### Non-stream responses

- 'BaseOpenAIProvider.generateResponse()' — extract 'response.usage.prompt_tokens' + 'response.usage.completion_tokens'
- 'GeminiNativeProvider.generateResponse()' — extract 'usageMetadata.promptTokenCount' + 'usageMetadata.candidatesTokenCount'
- If usage data is absent → 'usageDict = None'

### Stream responses

- Capture the final chunk containing usage metadata
- After streaming completes, yield a special event '{"type": "usage", "data": usageDict}'
- If the final chunk has no usage → 'usageDict = None'

### Fallback logic (at service layer)

- If 'usageDict is None' → count via tiktoken + log:
  'logger.warning(f"[TOKEN_SOURCE: tiktoken_fallback] Provider {model} did not return usage data, counting via tiktoken")'
- If usageDict present → log:
  'logger.info(f"[TOKEN_SOURCE: api_usage] {model}: prompt={promptTokens}, completion={completionTokens}")'

## Redis Quota Tracking

### Redis keys

'''
quota:session:{userId}:{conversationId}   → integer counter, TTL = TOKEN_SESSION_DURATION
quota:weekly:{userId}:{weekStart}         → integer counter, TTL = 7 days
'''

- 'weekStart' = Monday of current week (ISO date, e.g. '2026-03-30')

### Module structure

'''
modules/quota/
├── router.py       # GET /quota/status
├── service.py      # checkQuota, incrementUsage, getStatus, rebuildFromDb
└── repository.py   # Redis operations + DB rebuild queries
'''

### Core operations

- 'checkQuota(userId, conversationId)' → returns:
  '''python
  {
      "allowed": bool,
      "session": {"used": int, "limit": int, "percent": float},
      "weekly": {"used": int, "limit": int, "percent": float},
      "warning": bool
  }
  '''
- 'incrementUsage(userId, conversationId, tokens)' → INCRBY on both session and weekly keys
- 'getStatus(userId, conversationId)' → returns quota status for frontend
- 'rebuildFromDb(userId)' → when Redis key missing, query SUM of tokens from DB messages within the relevant time window, then SET the Redis counter

### Enforcement flow

1. 'checkQuota()' before calling LLM
2. If 'percent >= 1.0' → block with HTTP 429 + quota status
3. If 'percent >= warningThreshold' → attach 'warning: true' in response
4. After LLM response → 'incrementUsage()' with 'usage.totalTokens'

## Message Metadata (extended)

'''python
{
    "tokens": 150,                    # kept for backward compatibility
    "usage": {
        "promptTokens": 1200,
        "completionTokens": 150,
        "totalTokens": 1350,
        "source": "api_usage"
    }
}
'''

- 'metadata.tokens' remains = completion token count (backward compat with existing code)
- 'metadata.usage' = new detailed usage, used for quota tracking
- Quota increment uses 'usage.totalTokens' (prompt + completion)

## Frontend — Collapsible Quota Widget

### Component

'src/components/ui/QuotaWidget.jsx'

### Collapsed state

- Small circular icon at bottom-right corner of chat page
- Color changes by usage level: green (< 70%), yellow (70–90%), red (> 90%)
- Pulse animation when backend returns a warning

### Expanded state (click to toggle)

- Small popup panel with 2 progress bars:
  - **Session** — "Session: 125k / 500k tokens" + progress bar + remaining time "1h 23m remaining"
  - **Weekly** — "Weekly: 2.1M / 5M tokens" + progress bar + "Resets Mon"
- Progress bars change color: green → yellow → red
- Click outside or click icon again → collapse

### Block state (100%)

- Overlay message in chat input area: "Bạn đã hết quota. Vui lòng đợi [time]."
- Chat input disabled
- Widget auto-expands to show details

### Data flow

- Fetch 'GET /quota/status' on ChatPage mount
- Update after each message via quota info in the final SSE event
- No polling — event-driven only

## End-to-End Flow

'''
User sends message
  → Frontend POST /messages/chat/completions
  → Router calls quotaService.checkQuota(userId, convId)
    → Redis GET session + weekly counters
    → If key missing → rebuildFromDb()
  → If blocked → return 429 + quota status
  → If ok → call LLM (stream)
  → LLM returns chunks + usage in final chunk
  → messageRepository.create() saves message + usageDict in metadata
  → quotaService.incrementUsage(userId, convId, totalTokens)
  → SSE stream: text chunks → final "quota" event with updated status
  → Frontend updates QuotaWidget
'''

## Out of Scope

- Per-user configurable limits (admin sets via env for all users)
- Historical usage analytics dashboard
- Billing integration
