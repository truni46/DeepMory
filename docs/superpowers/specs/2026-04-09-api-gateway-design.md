# API Gateway Design

**Date:** 2026-04-09  
**Status:** Approved  

## Overview

Build an API gateway inside the existing FastAPI server to expose `api/v1` endpoints to third-party developers. Authentication uses `X-API-Key` header instead of JWT. Admin creates and manages API keys. Rate limiting is per-day per key. An Admin Portal (separate React layout at `/admin`) provides key management UI.

---

## Architecture

### Approach: FastAPI Middleware

A `GatewayMiddleware` intercepts every request to `/api/v1`. If the request carries an `X-API-Key` header, the middleware handles authentication, scope check, and quota enforcement. If there is no `X-API-Key`, the request falls through to the existing JWT auth — no changes to existing routers.

### Request Flow

```
Incoming request to /api/v1/*
    │
    ├── has X-API-Key header?
    │       YES → GatewayMiddleware:
    │               1. Lookup keyHash in Redis (TTL 60s)
    │               2. Cache miss → query DB, populate cache
    │               3. Verify key isActive + not expired
    │               4. Check scope allows this endpoint/method
    │               5. INCR Redis daily quota counter
    │               6. Counter > dailyQuota → 429 Too Many Requests
    │               7. Inject request.state.userId + request.state.apiKeyId
    │               8. Log usage to apiUsage table (async, non-blocking)
    │               9. Pass to router
    │
    └── no X-API-Key → existing JWT auth (unchanged)
```

### New Module: `server/modules/gateway/`

```
server/modules/gateway/
├── middleware.py      # GatewayMiddleware — intercepts X-API-Key requests
├── router.py          # Admin endpoints: CRUD API keys, usage stats
├── service.py         # validateKey, checkScope, checkQuota, trackUsage
└── repository.py      # DB operations for apiKeys and apiUsage tables
```

---

## Database Schema

All column names use camelCase in double-quotes per project convention.

```sql
-- API keys
CREATE TABLE "apiKeys" (
    "id"          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    "keyHash"     TEXT NOT NULL UNIQUE,   -- SHA-256 of plaintext key
    "keyPrefix"   VARCHAR(16) NOT NULL,   -- first 12 chars for UI display
    "name"        TEXT NOT NULL,
    "userId"      UUID NOT NULL REFERENCES users("id") ON DELETE CASCADE,
    "scopes"      JSONB NOT NULL DEFAULT '[]',
    "dailyQuota"  INTEGER,               -- NULL = unlimited
    "isActive"    BOOLEAN NOT NULL DEFAULT TRUE,
    "expiresAt"   TIMESTAMPTZ,
    "createdAt"   TIMESTAMPTZ NOT NULL DEFAULT now(),
    "updatedAt"   TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Usage log
CREATE TABLE "apiUsage" (
    "id"           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    "apiKeyId"     UUID NOT NULL REFERENCES "apiKeys"("id") ON DELETE CASCADE,
    "endpoint"     TEXT NOT NULL,
    "method"       VARCHAR(10) NOT NULL,
    "statusCode"   INTEGER NOT NULL,
    "requestedAt"  TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Add role to users table
ALTER TABLE users ADD COLUMN "role" VARCHAR(20) NOT NULL DEFAULT 'user';
UPDATE users SET "role" = 'admin' WHERE email = 'test@gmail.com';
```

### Redis Keys

```
gateway:key:{keyHash}          → JSON key metadata (TTL 60s)
gateway:quota:{keyId}:{date}   → daily request count integer (TTL 25h)
```

---

## API Key Format

Keys are generated as: `dm_live_<32 random chars>` (e.g. `dm_live_a1b2c3d4...`)

- Server stores only `SHA-256(key)` — plaintext is never persisted
- `keyPrefix` = first 12 characters, used for identification in UI
- Plaintext is returned only once at creation time

---

## Scopes

Each API key has a `scopes` array. The middleware checks the incoming request path and method against the allowed scope map:

| Scope | Allowed Endpoints |
|-------|-------------------|
| `messages` | `POST /messages/chat/completions`, `GET /messages/*` |
| `conversations` | `GET/POST/PATCH/DELETE /conversations/*` |
| `knowledge` | `POST /knowledge/upload`, `GET /knowledge/documents`, `DELETE /knowledge/documents/*` |
| `rag` | `POST /rag/search`, `POST /rag/memory/search` |
| `memory` | `GET/PATCH/DELETE /memory/*` |
| `agents` | `POST/GET/DELETE /agents/tasks/*`, `GET /agents/memories` |
| `projects` | `GET/POST /projects/*` |

Requests to endpoints not covered by the key's scopes return `403 Forbidden`.

---

## Admin Role

Field `"role"` on the `users` table. Values: `"admin"` | `"user"` (default `"user"`).

```python
async def requireAdmin(currentUser = Depends(getCurrentUser)):
    if currentUser["role"] != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")
    return currentUser
```

All `/api/v1/gateway/*` endpoints require `Depends(requireAdmin)`.

---

## Admin Endpoints (Phase 1 — Backend)

```
POST   /api/v1/gateway/keys                    # Create API key
GET    /api/v1/gateway/keys                    # List all keys
GET    /api/v1/gateway/keys/{keyId}            # Get key detail + today's usage count
PATCH  /api/v1/gateway/keys/{keyId}            # Update name, scopes, dailyQuota, isActive, expiresAt
DELETE /api/v1/gateway/keys/{keyId}            # Revoke and delete key
GET    /api/v1/gateway/keys/{keyId}/usage      # Usage history — supports ?groupBy=day&days=30 for chart aggregation, or raw paginated logs
```

### Create Key — Request & Response

```json
POST /api/v1/gateway/keys
{
  "name": "Partner ABC",
  "scopes": ["messages", "conversations"],
  "dailyQuota": 1000,
  "expiresAt": "2027-01-01T00:00:00Z"
}

Response 201:
{
  "id": "uuid",
  "key": "dm_live_a1b2c3d4...",   ← returned only once
  "keyPrefix": "dm_live_a1b2",
  "name": "Partner ABC",
  "scopes": ["messages", "conversations"],
  "dailyQuota": 1000,
  "isActive": true,
  "expiresAt": "2027-01-01T00:00:00Z",
  "createdAt": "..."
}
```

### Error Responses

| Scenario | HTTP Status |
|----------|-------------|
| Invalid or inactive key | `401 Unauthorized` |
| Scope not allowed for endpoint | `403 Forbidden` |
| Daily quota exceeded | `429 Too Many Requests` |
| Key expired | `401 Unauthorized` |

---

## Phase 2 — Admin Portal UI

### Separate Layout

Admin portal lives at `/admin/*` with its own React layout, completely separate from `ChatLayout`. No link from the main app — admin accesses directly via URL.

### File Structure

```
src/pages/admin/
├── AdminLayout.jsx         # Layout with sidebar + auth guard (role check)
├── AdminLoginPage.jsx      # Redirect to /login if not authenticated, then back to /admin
├── ApiKeysPage.jsx         # List all keys + create button
└── ApiKeyDetailPage.jsx    # Key detail, usage chart, edit form

src/components/admin/
├── AdminSidebar.jsx        # Navigation links for admin portal
├── ApiKeyTable.jsx         # Table: keyPrefix, name, scopes, quota, status, actions
├── CreateApiKeyModal.jsx   # Multi-step modal: form → copy plaintext key
├── ApiKeyScopeSelector.jsx # Checkbox group for scope selection
└── UsageChart.jsx          # Bar chart: requests per day (last 30 days)
```

### Routes

```
/admin                   → redirect to /admin/keys
/admin/keys              → ApiKeysPage
/admin/keys/:keyId       → ApiKeyDetailPage
```

`AdminLayout` checks `currentUser.role !== "admin"` and redirects to `/` if not admin.

### Create Key UX Flow

1. Admin clicks "Create API Key" → `CreateApiKeyModal` opens
2. Step 1 — Form: fill name, select scopes via `ApiKeyScopeSelector`, enter `dailyQuota` (optional), `expiresAt` (optional)
3. Submit → API call → server returns plaintext key
4. Step 2 — Copy screen: display full key with one-click copy button, warning "This key will not be shown again"
5. Admin closes modal → key removed from memory

### Usage Chart

`ApiKeyDetailPage` shows a bar chart of daily request counts for the past 30 days. The endpoint `GET /api/v1/gateway/keys/{keyId}/usage?groupBy=day&days=30` returns pre-aggregated data from the backend (count per day). Uses **Recharts** — needs to be added as a new dependency (`npm install recharts`).

---

## Implementation Phases

### Phase 1 — Backend

1. DB migration: add `"role"` to `users`, create `apiKeys` and `apiUsage` tables
2. `modules/gateway/repository.py` — CRUD for apiKeys, insert apiUsage, aggregate usage stats
3. `modules/gateway/service.py` — key generation, hash, validateKey, checkScope, checkQuota, trackUsage
4. `modules/gateway/middleware.py` — GatewayMiddleware, Redis cache + quota counter
5. `modules/gateway/router.py` — admin endpoints with `requireAdmin` dependency
6. Register middleware and router in `main.py` / `apiRouter.py`
7. `requireAdmin` dependency in `common/deps.py`

### Phase 2 — Frontend

1. Add `/admin` routes to React Router
2. `AdminLayout` with role guard
3. `ApiKeysPage` + `ApiKeyTable` + `CreateApiKeyModal` + `ApiKeyScopeSelector`
4. `ApiKeyDetailPage` + `UsageChart`
5. API service calls for gateway endpoints
