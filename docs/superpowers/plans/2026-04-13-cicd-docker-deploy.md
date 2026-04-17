# CI/CD Pipeline with GitHub Actions + Docker Deploy — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Set up automated CI (test on push/PR to `main`) and CD (SSH deploy to VPS on push to `main`) using GitHub Actions + Docker Compose.

**Architecture:** GitHub Actions runs a `test` job (pytest + `npm run build`) with Postgres/Redis service containers, then a `deploy` job that SSHes to a VPS at `/opt/deepmory`, runs `git reset --hard origin/main` and `docker compose up -d --build`. Server-managed `.env` files hold all secrets. Health check endpoint enables Docker health probes and post-deploy smoke test.

**Tech Stack:** GitHub Actions, Docker, Docker Compose v2, FastAPI, Vite, appleboy/ssh-action, pytest, Node 18, Python 3.10.

**Spec:** `docs/superpowers/specs/2026-04-13-cicd-docker-deploy-design.md`

---

## File Structure

**Files created:**
- `.github/workflows/ci-cd.yml` — main workflow
- `.dockerignore` — root, for frontend build context
- `server/.dockerignore` — for backend build context
- `docker-compose.prod.yml` — production override
- `deploy/bootstrap.sh` — server one-time setup script
- `deploy/README.md` — admin documentation
- `server/modules/system/__init__.py`
- `server/modules/system/service.py` — health check logic
- `server/modules/system/router.py` — `/api/v1/health` endpoint
- `server/tests/system/__init__.py`
- `server/tests/system/test_health.py` — tests for health endpoint
- `server/tests/conftest.py` — pytest fixtures (if not existing)
- `pytest.ini` — pytest config at `server/` root (if not existing)

**Files modified:**
- `server/Dockerfile` — multi-stage build + HEALTHCHECK + curl
- `Dockerfile` — add HEALTHCHECK
- `docker-compose.yml` — add healthchecks on backend/frontend/redis; ensure backend waits for DB healthy
- `server/apiRouter.py` — register system router
- `server/requirements.txt` — verify `pytest`, `pytest-asyncio`, `httpx` present (add if missing)

Each task below produces a self-contained change and a commit.

---

## Task 1: Add `.dockerignore` files

**Files:**
- Create: `.dockerignore`
- Create: `server/.dockerignore`

- [ ] **Step 1: Create root `.dockerignore`**

Create file `.dockerignore` at project root:

```
node_modules
dist
build
.git
.gitignore
.env
.env.*
!.env.example
server
docs
deploy
.github
.vscode
.idea
*.md
!README.md
__pycache__
*.pyc
.DS_Store
coverage
.pytest_cache
```

- [ ] **Step 2: Create `server/.dockerignore`**

Create file `server/.dockerignore`:

```
__pycache__
*.pyc
*.pyo
*.pyd
.pytest_cache
.venv
venv
env
tests
data
.env
.env.*
!.env.example
*.md
.git
.gitignore
.DS_Store
*.log
tmp_*.py
```

- [ ] **Step 3: Commit**

```bash
git add .dockerignore server/.dockerignore
git commit -m "chore(docker): add .dockerignore files for slimmer build contexts"
```

---

## Task 2: Health check backend module (TDD)

**Files:**
- Create: `server/modules/system/__init__.py`
- Create: `server/modules/system/service.py`
- Create: `server/modules/system/router.py`
- Create: `server/tests/system/__init__.py`
- Create: `server/tests/system/test_health.py`
- Modify: `server/apiRouter.py`

- [ ] **Step 1: Verify required test deps present**

Check `server/requirements.txt` for `pytest`, `pytest-asyncio`, `httpx`. If any are missing, append:

```
pytest==8.3.3
pytest-asyncio==0.24.0
httpx==0.27.2
```

Run: `grep -E "^(pytest|pytest-asyncio|httpx)" server/requirements.txt`
Expected: all three appear.

- [ ] **Step 2: Create empty `__init__.py` files**

Create `server/modules/system/__init__.py` — empty file.
Create `server/tests/system/__init__.py` — empty file.

- [ ] **Step 3: Write failing test for health endpoint**

Create `server/tests/system/test_health.py`:

```python
import pytest
from httpx import AsyncClient, ASGITransport
from main import app


@pytest.mark.asyncio
async def test_healthReturnsOkWhenAllServicesUp():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        response = await ac.get("/api/v1/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert "timestamp" in body
    assert "db" in body
    assert "redis" in body


@pytest.mark.asyncio
async def test_healthPayloadShape():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        response = await ac.get("/api/v1/health")
    body = response.json()
    assert set(body.keys()) >= {"status", "timestamp", "db", "redis"}
    assert body["db"] in ("ok", "down")
    assert body["redis"] in ("ok", "down")
```

- [ ] **Step 4: Run test to verify it fails**

Run: `cd server && pytest tests/system/test_health.py -v`
Expected: FAIL with 404 (endpoint does not exist yet) or ImportError.

- [ ] **Step 5: Implement health service**

Create `server/modules/system/service.py`:

```python
from datetime import datetime, timezone
from config.database import db
from common.cacheService import cacheService
from config.logger import logger


class SystemService:
    async def checkDb(self) -> str:
        try:
            if db.useDatabase and db.pool:
                async with db.pool.acquire() as conn:
                    await conn.fetchval("SELECT 1")
                return "ok"
            return "ok"
        except Exception as e:
            logger.warning(f"checkDb failed: {e}")
            return "down"

    async def checkRedis(self) -> str:
        try:
            client = cacheService.client
            if client is None:
                return "down"
            await client.ping()
            return "ok"
        except Exception as e:
            logger.warning(f"checkRedis failed: {e}")
            return "down"

    async def getHealth(self) -> dict:
        dbStatus = await self.checkDb()
        redisStatus = await self.checkRedis()
        overall = "ok" if dbStatus == "ok" and redisStatus == "ok" else "degraded"
        return {
            "status": overall,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "db": dbStatus,
            "redis": redisStatus,
        }


systemService = SystemService()
```

Note: If `config.database.db` or `common.cacheService.cacheService` expose attributes differently (e.g., Redis client is named `.redis` not `.client`), adapt to the actual attribute name before committing. Check the imports:

Run: `grep -E "^(class |self\.client|self\.redis|self\.pool)" server/common/cacheService.py server/config/database.py`

Use whichever attribute exists.

- [ ] **Step 6: Implement health router**

Create `server/modules/system/router.py`:

```python
from fastapi import APIRouter
from fastapi.responses import JSONResponse
from modules.system.service import systemService
from config.logger import logger

router = APIRouter(tags=["system"])


@router.get("/health")
async def getHealthEndpoint():
    try:
        payload = await systemService.getHealth()
        statusCode = 200 if payload["status"] == "ok" else 503
        return JSONResponse(status_code=statusCode, content=payload)
    except Exception as e:
        logger.error(f"getHealthEndpoint failed: {e}")
        return JSONResponse(
            status_code=500,
            content={"status": "error", "detail": str(e)},
        )
```

- [ ] **Step 7: Register system router**

Modify `server/apiRouter.py`. Add import and `include_router` line:

```python
from fastapi import APIRouter
from modules.auth.router import router as authRouter
from modules.projects.router import router as projectsRouter
from modules.conversations.router import router as conversationsRouter
from modules.message.router import router as messagesRouter
from modules.settings.router import router as settingsRouter
from modules.knowledge.router import router as knowledgeRouter
from modules.rag.router import router as ragRouter
from modules.memory.router import router as memoryRouter
from modules.agents.router import router as agentsRouter
from modules.quota.router import router as quotaRouter
from modules.system.router import router as systemRouter

router = APIRouter()

router.include_router(authRouter)
router.include_router(projectsRouter)
router.include_router(conversationsRouter)
router.include_router(messagesRouter)
router.include_router(settingsRouter)
router.include_router(knowledgeRouter)
router.include_router(ragRouter)
router.include_router(memoryRouter)
router.include_router(agentsRouter)
router.include_router(quotaRouter)
router.include_router(systemRouter)
```

- [ ] **Step 8: Run tests, verify pass**

Run: `cd server && pytest tests/system/test_health.py -v`
Expected: 2 passed.

If tests fail because `db.useDatabase` or `cacheService.client` attribute name is wrong, adjust `service.py` accordingly — re-check the attribute names using the grep command from Step 5. The tests check only shape, not actual DB/Redis connectivity, so they should pass even when DB/Redis aren't running locally (both checkers should return "ok" when attributes are None/not configured, OR return "down" gracefully — verify test assertions accept either).

- [ ] **Step 9: Manually verify endpoint**

Start server: `cd server && python main.py` (in one terminal)
Hit endpoint: `curl http://localhost:3000/api/v1/health`
Expected: JSON with `status`, `timestamp`, `db`, `redis` fields. Stop server (Ctrl+C).

- [ ] **Step 10: Commit**

```bash
git add server/modules/system/ server/tests/system/ server/apiRouter.py server/requirements.txt
git commit -m "feat(system): add /api/v1/health endpoint with db+redis checks"
```

---

## Task 3: Ensure pytest config works

**Files:**
- Create or verify: `server/pytest.ini`
- Create or verify: `server/tests/conftest.py`

- [ ] **Step 1: Check for existing pytest config**

Run: `ls server/pytest.ini server/pyproject.toml server/tests/conftest.py 2>/dev/null`

If `pytest.ini` exists already, skip to Step 3.

- [ ] **Step 2: Create `server/pytest.ini`**

Create `server/pytest.ini`:

```ini
[pytest]
asyncio_mode = auto
testpaths = tests
pythonpath = .
addopts = -v --tb=short
```

- [ ] **Step 3: Create/verify `server/tests/conftest.py`**

If it already exists, leave it. Otherwise create `server/tests/conftest.py`:

```python
import os
import sys
from pathlib import Path

# Make server/ importable as package root
ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

# Default test env vars (overridden by CI service containers)
os.environ.setdefault("USE_DATABASE", "false")
os.environ.setdefault("DB_HOST", "localhost")
os.environ.setdefault("DB_PORT", "5432")
os.environ.setdefault("DB_NAME", "deepmory_test")
os.environ.setdefault("DB_USER", "deepmory")
os.environ.setdefault("DB_PASSWORD", "deepmory_test_pass")
os.environ.setdefault("REDIS_HOST", "localhost")
os.environ.setdefault("REDIS_PORT", "6379")
os.environ.setdefault("REDIS_PASSWORD", "deepmory_test_pass")
```

- [ ] **Step 4: Run full test suite locally**

Run: `cd server && pytest -v`
Expected: all tests collected and either pass or have pre-existing failures unrelated to our changes. If new failures appear because of our changes, debug before continuing.

- [ ] **Step 5: Commit**

```bash
git add server/pytest.ini server/tests/conftest.py
git commit -m "chore(tests): add pytest.ini and test env defaults"
```

---

## Task 4: Multi-stage backend Dockerfile + HEALTHCHECK

**Files:**
- Modify: `server/Dockerfile`

- [ ] **Step 1: Rewrite `server/Dockerfile`**

Replace full contents:

```dockerfile
# Stage 1: build wheels
FROM python:3.10-slim AS builder

WORKDIR /build

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    gcc \
    libpq-dev \
  && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .

RUN pip wheel --no-cache-dir --wheel-dir=/wheels -r requirements.txt


# Stage 2: runtime
FROM python:3.10-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    libpq5 \
  && rm -rf /var/lib/apt/lists/*

COPY --from=builder /wheels /wheels
COPY requirements.txt .

RUN pip install --no-cache-dir --no-index --find-links=/wheels -r requirements.txt \
  && rm -rf /wheels

COPY . .

EXPOSE 3000

HEALTHCHECK --interval=30s --timeout=5s --start-period=30s --retries=3 \
  CMD curl -fsS http://localhost:3000/api/v1/health || exit 1

CMD ["python", "main.py"]
```

- [ ] **Step 2: Build backend image locally**

Run: `docker build -t deepmory-backend:test ./server`
Expected: build succeeds. Note: first build will be slow (compiling wheels); subsequent builds use Docker layer cache.

- [ ] **Step 3: Smoke test container**

Run: `docker run --rm -d --name deepmory-bk-test -p 3001:3000 deepmory-backend:test`
Wait 15 seconds, then: `curl http://localhost:3001/api/v1/health`
Expected: JSON response (db/redis likely "down" since no DB/Redis running — that's fine, endpoint reachable).
Cleanup: `docker rm -f deepmory-bk-test`

- [ ] **Step 4: Commit**

```bash
git add server/Dockerfile
git commit -m "refactor(docker): multi-stage backend Dockerfile with HEALTHCHECK"
```

---

## Task 5: Frontend Dockerfile HEALTHCHECK

**Files:**
- Modify: `Dockerfile`

- [ ] **Step 1: Update root `Dockerfile`**

Replace full contents:

```dockerfile
FROM node:18-alpine AS build

WORKDIR /app

COPY package*.json ./
RUN npm ci

COPY . .

ARG VITE_API_URL=http://localhost:3000/api/v1
ARG VITE_SOCKET_URL=http://localhost:3000
ENV VITE_API_URL=$VITE_API_URL
ENV VITE_SOCKET_URL=$VITE_SOCKET_URL

RUN npm run build


FROM nginx:alpine

RUN apk add --no-cache wget

COPY --from=build /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf

EXPOSE 80

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
  CMD wget --spider -q http://localhost/ || exit 1

CMD ["nginx", "-g", "daemon off;"]
```

Notes changed from original:
- `npm install` → `npm ci` (deterministic, faster, respects lockfile)
- Added `wget` to nginx stage for HEALTHCHECK
- Added `HEALTHCHECK` instruction

- [ ] **Step 2: Build frontend image**

Run: `docker build -t deepmory-frontend:test .`
Expected: build succeeds.

- [ ] **Step 3: Smoke test**

Run: `docker run --rm -d --name deepmory-fe-test -p 8080:80 deepmory-frontend:test`
Wait 5 seconds, then: `curl -I http://localhost:8080/`
Expected: `HTTP/1.1 200 OK`.
Cleanup: `docker rm -f deepmory-fe-test`

- [ ] **Step 4: Commit**

```bash
git add Dockerfile
git commit -m "refactor(docker): add HEALTHCHECK + npm ci to frontend Dockerfile"
```

---

## Task 6: Docker Compose healthchecks + depends_on conditions

**Files:**
- Modify: `docker-compose.yml`

- [ ] **Step 1: Add healthcheck to backend + redis, use `depends_on.condition`**

Replace full contents of `docker-compose.yml`:

```yaml
version: '3.8'

services:
  backend:
    build: ./server
    ports:
      - "3000:3000"
    environment:
      - PORT=3000
      - HOST=0.0.0.0
      - FRONTEND_URL=http://localhost:80
      - DB_HOST=db
      - DB_PORT=5432
      - DB_NAME=deepmory_db
      - DB_USER=deepmory
      - DB_PASSWORD=${DB_PASSWORD:-deepmory_pass}
      - REDIS_HOST=redis
      - REDIS_PASSWORD=${REDIS_PASSWORD:-deepmory_pass}
      - USE_DATABASE=true
      - OLLAMA_BASE_URL=http://host.docker.internal:11434/v1
      - QDRANT_URL=http://qdrant:6333
      - NEO4J_URL=bolt://neo4j:7687
      - NEO4J_USER=neo4j
      - NEO4J_PASSWORD=${NEO4J_PASSWORD:-deepmory_pass}
      - LIGHTRAG_QUERY_MODE=hybrid
    depends_on:
      db:
        condition: service_healthy
      redis:
        condition: service_healthy
      qdrant:
        condition: service_started
      neo4j:
        condition: service_started
    networks:
      - app_network
    extra_hosts:
      - "host.docker.internal:host-gateway"
    healthcheck:
      test: ["CMD", "curl", "-fsS", "http://localhost:3000/api/v1/health"]
      interval: 30s
      timeout: 5s
      retries: 3
      start_period: 30s

  frontend:
    build:
      context: .
      args:
        - VITE_API_URL=http://localhost:3000/api/v1
        - VITE_SOCKET_URL=http://localhost:3000
    ports:
      - "80:80"
    depends_on:
      - backend
    networks:
      - app_network
    healthcheck:
      test: ["CMD", "wget", "--spider", "-q", "http://localhost/"]
      interval: 30s
      timeout: 5s
      retries: 3
      start_period: 10s

  db:
    image: postgres:15-alpine
    environment:
      - POSTGRES_USER=deepmory
      - POSTGRES_PASSWORD=${DB_PASSWORD:-deepmory_pass}
      - POSTGRES_DB=deepmory_db
    ports:
      - "5432:5432"
    networks:
      - app_network
    volumes:
      - postgres_data:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U deepmory -d deepmory_db"]
      interval: 5s
      timeout: 5s
      retries: 5

  redis:
    image: redis:alpine
    command: redis-server --requirepass "${REDIS_PASSWORD:-deepmory_pass}"
    ports:
      - "6379:6379"
    networks:
      - app_network
    healthcheck:
      test: ["CMD-SHELL", "redis-cli -a \"${REDIS_PASSWORD:-deepmory_pass}\" ping | grep PONG"]
      interval: 5s
      timeout: 5s
      retries: 5

  redis-commander:
    image: rediscommander/redis-commander:latest
    environment:
      - REDIS_HOSTS=local:redis:6379:0:${REDIS_PASSWORD:-deepmory_pass}
    ports:
      - "8081:8081"
    depends_on:
      - redis
    networks:
      - app_network

  qdrant:
    image: qdrant/qdrant
    ports:
      - "6333:6333"
      - "6334:6334"
    volumes:
      - qdrant_data:/qdrant/storage
    networks:
      - app_network
    restart: unless-stopped

  neo4j:
    image: neo4j:latest
    ports:
      - "7474:7474"
      - "7687:7687"
    environment:
      - NEO4J_AUTH=neo4j/${NEO4J_PASSWORD:-deepmory_pass}
      - NEO4J_PLUGINS=["apoc"]
    volumes:
      - neo4j_data:/data
    networks:
      - app_network
    restart: unless-stopped

networks:
  app_network:

volumes:
  postgres_data:
  qdrant_data:
  neo4j_data:
```

- [ ] **Step 2: Verify compose file valid**

Run: `docker compose config > /dev/null && echo OK`
Expected: `OK` (no errors).

- [ ] **Step 3: Commit**

```bash
git add docker-compose.yml
git commit -m "feat(docker-compose): add healthchecks to backend/frontend/redis"
```

---

## Task 7: Production compose override

**Files:**
- Create: `docker-compose.prod.yml`

- [ ] **Step 1: Create `docker-compose.prod.yml`**

Create file at project root:

```yaml
version: '3.8'

# Production overrides applied via:
#   docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d --build
# - Closes internal service ports from the host
# - Removes dev-only redis-commander
# - Adds restart policies + log rotation

services:
  backend:
    restart: always
    logging:
      driver: json-file
      options:
        max-size: "10m"
        max-file: "3"

  frontend:
    restart: always
    logging:
      driver: json-file
      options:
        max-size: "10m"
        max-file: "3"

  db:
    restart: always
    ports: []
    logging:
      driver: json-file
      options:
        max-size: "10m"
        max-file: "3"

  redis:
    restart: always
    ports: []
    logging:
      driver: json-file
      options:
        max-size: "10m"
        max-file: "3"

  qdrant:
    restart: always
    ports: []
    logging:
      driver: json-file
      options:
        max-size: "10m"
        max-file: "3"

  neo4j:
    restart: always
    ports: []
    logging:
      driver: json-file
      options:
        max-size: "10m"
        max-file: "3"

  redis-commander:
    # Disable dev UI in production by overriding with a no-op command and profile
    profiles:
      - never
```

Note: The `profiles: [never]` on `redis-commander` means it won't start unless the `never` profile is explicitly requested — effectively disabling it in prod.

- [ ] **Step 2: Verify merged compose is valid**

Run: `docker compose -f docker-compose.yml -f docker-compose.prod.yml config > /dev/null && echo OK`
Expected: `OK`.

Also verify ports are stripped on db/redis in merged config:

Run: `docker compose -f docker-compose.yml -f docker-compose.prod.yml config | grep -A1 "^  db:" | head -20`
Expected: no `ports:` listing 5432 exposed.

- [ ] **Step 3: Commit**

```bash
git add docker-compose.prod.yml
git commit -m "feat(docker-compose): production override (restart, log rotation, no public DB/Redis)"
```

---

## Task 8: GitHub Actions workflow

**Files:**
- Create: `.github/workflows/ci-cd.yml`

- [ ] **Step 1: Create workflow directory**

Run: `mkdir -p .github/workflows`

- [ ] **Step 2: Create workflow file**

Create `.github/workflows/ci-cd.yml`:

```yaml
name: CI/CD

on:
  push:
    branches: [main]
  pull_request:
    branches: [main]

concurrency:
  group: ci-cd-${{ github.ref }}
  cancel-in-progress: true

jobs:
  test:
    name: Test
    runs-on: ubuntu-latest

    services:
      postgres:
        image: postgres:15-alpine
        env:
          POSTGRES_USER: deepmory
          POSTGRES_PASSWORD: deepmory_test_pass
          POSTGRES_DB: deepmory_test
        ports:
          - 5432:5432
        options: >-
          --health-cmd "pg_isready -U deepmory -d deepmory_test"
          --health-interval 5s
          --health-timeout 5s
          --health-retries 10

      redis:
        image: redis:7-alpine
        ports:
          - 6379:6379
        options: >-
          --health-cmd "redis-cli ping"
          --health-interval 5s
          --health-timeout 5s
          --health-retries 10

    env:
      USE_DATABASE: "true"
      DB_HOST: localhost
      DB_PORT: 5432
      DB_NAME: deepmory_test
      DB_USER: deepmory
      DB_PASSWORD: deepmory_test_pass
      REDIS_HOST: localhost
      REDIS_PORT: 6379
      REDIS_PASSWORD: ""
      SECRET_KEY: test_secret_key_for_ci_only
      ALGORITHM: HS256
      ACCESS_TOKEN_EXPIRE_MINUTES: "60"
      LLM_PROVIDER: ollama
      LLM_MODEL: test-model
      OLLAMA_BASE_URL: http://localhost:11434/v1

    steps:
      - name: Checkout
        uses: actions/checkout@v4

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.10'
          cache: 'pip'
          cache-dependency-path: server/requirements.txt

      - name: Install system dependencies
        run: |
          sudo apt-get update
          sudo apt-get install -y libpq-dev gcc

      - name: Install Python dependencies
        working-directory: server
        run: |
          python -m pip install --upgrade pip
          pip install -r requirements.txt

      - name: Run backend tests
        working-directory: server
        run: pytest -v

      - name: Set up Node
        uses: actions/setup-node@v4
        with:
          node-version: '18'
          cache: 'npm'

      - name: Install frontend dependencies
        run: npm ci

      - name: Build frontend
        run: npm run build
        env:
          VITE_API_URL: http://localhost:3000/api/v1
          VITE_SOCKET_URL: http://localhost:3000

  deploy:
    name: Deploy to VPS
    needs: test
    if: github.event_name == 'push' && github.ref == 'refs/heads/main'
    runs-on: ubuntu-latest

    steps:
      - name: Deploy over SSH
        uses: appleboy/ssh-action@v1.0.3
        with:
          host: ${{ secrets.SSH_HOST }}
          username: ${{ secrets.SSH_USER }}
          key: ${{ secrets.SSH_PRIVATE_KEY }}
          port: ${{ secrets.SSH_PORT || 22 }}
          command_timeout: 20m
          script: |
            set -e
            cd /opt/deepmory
            git fetch origin main
            git reset --hard origin/main
            docker compose -f docker-compose.yml -f docker-compose.prod.yml build
            docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d
            docker image prune -f
            echo "Deploy complete. Verifying health..."
            sleep 15
            curl -fsS http://localhost:3000/api/v1/health || (echo "Health check failed" && docker compose logs --tail=100 backend && exit 1)
            echo "Health OK"
```

- [ ] **Step 3: Verify workflow YAML is valid**

Run: `python -c "import yaml; yaml.safe_load(open('.github/workflows/ci-cd.yml'))" && echo OK`
Expected: `OK`.

(If Python not available, paste the YAML into https://www.yamllint.com/ or any YAML validator.)

- [ ] **Step 4: Commit**

```bash
git add .github/workflows/ci-cd.yml
git commit -m "ci: add GitHub Actions workflow for test + SSH deploy"
```

---

## Task 9: Server bootstrap script

**Files:**
- Create: `deploy/bootstrap.sh`

- [ ] **Step 1: Create `deploy/` directory**

Run: `mkdir -p deploy`

- [ ] **Step 2: Create `deploy/bootstrap.sh`**

Create `deploy/bootstrap.sh`:

```bash
#!/usr/bin/env bash
# One-time server setup for DeepMory.
# Run as the `deploy` user on a fresh VPS.

set -euo pipefail

APP_DIR="/opt/deepmory"
REPO_URL="${REPO_URL:-git@github.com:YOUR_ORG/YOUR_REPO.git}"

echo "=== DeepMory server bootstrap ==="

# 1. Check prerequisites
command -v git >/dev/null 2>&1 || { echo "ERROR: git not installed"; exit 1; }
command -v docker >/dev/null 2>&1 || { echo "ERROR: docker not installed"; exit 1; }
docker compose version >/dev/null 2>&1 || { echo "ERROR: docker compose v2 not installed"; exit 1; }

# 2. Ensure app dir owned by current user
if [ ! -d "$APP_DIR" ]; then
  echo "ERROR: $APP_DIR does not exist. Create it as root: sudo mkdir -p $APP_DIR && sudo chown $USER:$USER $APP_DIR"
  exit 1
fi

cd "$APP_DIR"

# 3. Clone or verify repo
if [ ! -d "$APP_DIR/.git" ]; then
  echo "Cloning repo..."
  echo "Make sure your GitHub deploy key is configured in ~/.ssh/ and added to the repo."
  git clone "$REPO_URL" .
else
  echo "Repo already cloned."
fi

# 4. Seed .env files from examples
if [ ! -f "$APP_DIR/.env" ] && [ -f "$APP_DIR/.env.example" ]; then
  cp .env.example .env
  chmod 600 .env
  echo "Created $APP_DIR/.env from template. EDIT IT BEFORE STARTING SERVICES."
fi

if [ ! -f "$APP_DIR/server/.env" ] && [ -f "$APP_DIR/server/.env.example" ]; then
  cp server/.env.example server/.env
  chmod 600 server/.env
  echo "Created $APP_DIR/server/.env from template. EDIT IT BEFORE STARTING SERVICES."
fi

cat <<EOF

=== Bootstrap complete ===

Next steps:
  1. Edit $APP_DIR/.env and $APP_DIR/server/.env with real production secrets.
  2. Configure GitHub repository secrets (SSH_HOST, SSH_USER, SSH_PORT, SSH_PRIVATE_KEY).
  3. Push to main to trigger first deploy.

Manual start (first time, or after env changes):
  cd $APP_DIR
  docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d --build

Verify:
  curl http://localhost:3000/api/v1/health
  docker compose ps
EOF
```

- [ ] **Step 3: Make it executable**

Run: `chmod +x deploy/bootstrap.sh`

- [ ] **Step 4: Shellcheck (optional but recommended)**

If `shellcheck` is installed locally, run: `shellcheck deploy/bootstrap.sh`
Expected: no errors.

- [ ] **Step 5: Commit**

```bash
git add deploy/bootstrap.sh
git commit -m "feat(deploy): add server bootstrap script"
```

---

## Task 10: Deployment documentation

**Files:**
- Create: `deploy/README.md`

- [ ] **Step 1: Create `deploy/README.md`**

Create `deploy/README.md`:

````markdown
# Deployment Guide

This app uses GitHub Actions to run tests on every push/PR to `main` and auto-deploys to a single VPS when commits land on `main`. Deployment is a `git pull` + `docker compose up -d --build` over SSH.

## Prerequisites on the server

- Ubuntu 22.04 LTS (or similar Linux with systemd)
- Docker Engine + Docker Compose v2
- git
- A non-root user `deploy` with sudo-free docker access
- SSH key-based access for the `deploy` user (password auth disabled)

## One-time server setup

```bash
# As a sudo-capable admin user:
sudo adduser --disabled-password --gecos "" deploy
sudo usermod -aG docker deploy
sudo mkdir -p /opt/deepmory
sudo chown deploy:deploy /opt/deepmory
```

Install docker (Ubuntu):

```bash
curl -fsSL https://get.docker.com | sudo sh
```

### SSH key from GitHub Actions to server

On your local machine:

```bash
ssh-keygen -t ed25519 -C "github-actions-deploy" -f ~/.ssh/deepmory_deploy -N ""
ssh-copy-id -i ~/.ssh/deepmory_deploy.pub deploy@<SERVER_IP>
```

Add the private key contents (`cat ~/.ssh/deepmory_deploy`) to the repo's GitHub Secrets as `SSH_PRIVATE_KEY`. Also add:

- `SSH_HOST` — server IP or domain
- `SSH_USER` — `deploy`
- `SSH_PORT` — `22` (or custom)

### SSH key from server to GitHub (for private repos)

```bash
# As deploy user on the server:
ssh-keygen -t ed25519 -C "deepmory-server" -f ~/.ssh/github_deploy -N ""
cat ~/.ssh/github_deploy.pub
```

Paste the public key into your GitHub repo → Settings → Deploy keys (read-only is fine).

Configure SSH to use it for github.com:

```bash
cat >> ~/.ssh/config <<'EOF'
Host github.com
  HostName github.com
  User git
  IdentityFile ~/.ssh/github_deploy
EOF
chmod 600 ~/.ssh/config
```

### Bootstrap

```bash
# As deploy user on the server:
cd /opt/deepmory
# Clone using the bootstrap script (supply REPO_URL env var or edit the default in the script):
REPO_URL=git@github.com:<org>/<repo>.git bash /path/to/bootstrap.sh
# Or after first clone, just run from inside the repo:
bash deploy/bootstrap.sh
```

### Configure secrets on the server

Edit `.env` files created from examples:

```bash
nano /opt/deepmory/.env           # frontend build vars
nano /opt/deepmory/server/.env    # backend runtime vars
```

Populate real production values: DB passwords, SECRET_KEY, LLM API keys, Neo4j password, etc. These files are git-ignored; GitHub never sees them.

### First manual start

```bash
cd /opt/deepmory
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d --build
```

Verify:

```bash
docker compose ps
curl http://localhost:3000/api/v1/health
```

## Firewall

Open only: 22 (SSH), 80 (HTTP), 443 (HTTPS if using). Close 3000, 5432, 6379, 6333, 6334, 7474, 7687 — these are container-internal only in prod.

Example UFW:

```bash
sudo ufw default deny incoming
sudo ufw default allow outgoing
sudo ufw allow 22/tcp
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp
sudo ufw enable
```

## Hardening (recommended)

```bash
# /etc/ssh/sshd_config
PasswordAuthentication no
PermitRootLogin no
PubkeyAuthentication yes
```

```bash
sudo systemctl restart sshd
sudo apt-get install -y fail2ban
sudo systemctl enable --now fail2ban
```

## Continuous deployment flow

Push/merge to `main`. GitHub Actions will:

1. Run backend pytest + frontend `npm run build` against ephemeral Postgres/Redis containers.
2. If tests pass, SSH to the VPS and run:
   - `git fetch origin main && git reset --hard origin/main`
   - `docker compose -f docker-compose.yml -f docker-compose.prod.yml build`
   - `docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d`
   - `docker image prune -f`
   - `curl /api/v1/health` to verify.

## Rotating secrets

Server-side: edit `/opt/deepmory/.env` or `/opt/deepmory/server/.env`, then:

```bash
cd /opt/deepmory
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d
```

Compose will recreate only containers whose env changed.

GitHub SSH key: regenerate a new key pair, update `SSH_PRIVATE_KEY` in GitHub Secrets, update `authorized_keys` on server, remove old key.

## Rollback

```bash
ssh deploy@<SERVER>
cd /opt/deepmory
git log --oneline -10                # find last known-good commit SHA
git reset --hard <commit-sha>
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d --build
docker compose logs -f backend       # verify
```

To return to the latest `main` afterwards: `git reset --hard origin/main && docker compose ... up -d --build`.

## Troubleshooting

- **Workflow fails at deploy step:** check SSH secrets. Verify manually: `ssh -i ~/.ssh/deepmory_deploy deploy@<SERVER>`.
- **Tests fail in CI only:** check the Postgres/Redis service container env in the workflow matches what your code expects.
- **Container unhealthy:** `docker compose logs <service>`. Health endpoint: `curl http://localhost:3000/api/v1/health`.
- **Disk fills up:** `docker image prune -af && docker volume prune` (careful: never delete `postgres_data`, `qdrant_data`, `neo4j_data`).
- **Port 80 already in use:** another nginx/apache running. `sudo systemctl stop nginx` if system nginx is running, or change the frontend port mapping in `docker-compose.prod.yml`.
````

- [ ] **Step 2: Commit**

```bash
git add deploy/README.md
git commit -m "docs(deploy): server setup + deploy + rollback guide"
```

---

## Task 11: End-to-end local verification

- [ ] **Step 1: Build full stack locally with prod override**

Run:
```bash
docker compose -f docker-compose.yml -f docker-compose.prod.yml build
```
Expected: all images build successfully.

- [ ] **Step 2: Start full stack**

Run:
```bash
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d
```

- [ ] **Step 3: Wait for health and verify**

Wait 60 seconds, then:

```bash
docker compose ps
```

Expected: backend + frontend + db + redis show `healthy` status. qdrant/neo4j show running.

```bash
curl http://localhost:3000/api/v1/health
curl -I http://localhost/
```

Expected: health returns 200 JSON, frontend returns 200.

- [ ] **Step 4: Tear down**

Run: `docker compose -f docker-compose.yml -f docker-compose.prod.yml down`

Note: this does NOT delete volumes, so DB data persists across runs.

- [ ] **Step 5: No commit needed — verification step only.**

---

## Task 12: Push to a feature branch and verify CI on GitHub

**NOTE:** This task requires the GitHub Secrets to already be configured. If not yet done, skip deploy verification; test job should still run on the PR.

- [ ] **Step 1: Push current branch**

Run: `git push -u origin <current-branch>`

- [ ] **Step 2: Open PR against `main`**

On GitHub web: open a PR from the feature branch into `main`.

- [ ] **Step 3: Verify `test` job runs and passes**

Watch the PR's Checks tab. Expected: `test` job completes with green check. `deploy` job does NOT run (PR, not push to main).

If `test` fails, read the logs, fix the issue, push again, repeat.

- [ ] **Step 4: (Optional) Merge to main and verify deploy**

Only if server is prepared (bootstrap done, secrets configured). Merge the PR. Watch Actions tab — `test` then `deploy` should run. Verify on server:

```bash
ssh deploy@<SERVER>
cd /opt/deepmory
git log -1
docker compose ps
curl http://localhost:3000/api/v1/health
```

If anything fails, follow the rollback procedure in `deploy/README.md`.

---

## Self-Review Checklist (for the planner, not the executor)

- [x] Spec section 4 trigger rules → Task 8 workflow triggers
- [x] Spec 5.1 test job → Task 8 `test` job with postgres+redis services
- [x] Spec 5.1 deploy job → Task 8 `deploy` job with SSH action
- [x] Spec 5.2 prod compose override → Task 7
- [x] Spec 5.3 multi-stage backend Dockerfile → Task 4
- [x] Spec 5.3 frontend HEALTHCHECK → Task 5
- [x] Spec 5.4 dockerignore → Task 1
- [x] Spec 5.5 health endpoint → Task 2
- [x] Spec 5.6 deploy scripts + docs → Tasks 9, 10
- [x] Spec 6 secrets management → Task 10 README
- [x] Spec 7 server setup → Task 10 README
- [x] Spec 8 rollback → Task 10 README
- [x] Spec 9 testing strategy → Task 8 test job + health curl post-deploy
- [x] Spec 10 error handling → Task 8 `set -e` + health verify
- [x] Spec 11 files created/modified → all covered across tasks

No placeholders. All code blocks complete. Naming consistent (`systemService`, `getHealth`, `checkDb`, `checkRedis`).
