# CI/CD Pipeline with GitHub Actions + Docker Deploy — Design Spec

**Date:** 2026-04-13
**Status:** Draft — awaiting user review
**Scope:** Automate test + deploy of DeepMory full-stack app to a single VPS using GitHub Actions and Docker Compose.

---

## 1. Goals

- Auto-run tests (backend pytest + frontend build) on every push/PR to `main`.
- Auto-deploy to production VPS when code is merged to `main` and tests pass.
- Zero-downtime redeploy where possible (rolling container restart, persistent volumes).
- Secrets never leave the server. GitHub only holds SSH credentials.
- Provide documented rollback path.

## 2. Non-Goals

- Multi-environment (staging/prod) — out of scope for now.
- Blue/green or canary deployments — out of scope.
- Kubernetes / Docker Swarm orchestration — single VPS only.
- Auto rollback on health-check failure — manual rollback only.
- Frontend unit tests — no test suite exists yet.

## 3. Architecture Overview

```
Developer push/PR → main branch
        │
        ▼
GitHub Actions (.github/workflows/ci-cd.yml)
   │
   ├─ Job: test  (runs on push + PR)
   │    services: postgres:15-alpine, redis:7-alpine
   │    steps: setup Python → pytest → setup Node → npm ci → npm run build
   │
   └─ Job: deploy  (runs only on push to main, needs: test)
        steps: SSH into VPS → git pull → docker compose up -d --build → prune
                    │
                    ▼
             VPS (/opt/deepmory)
             ├─ git working tree (source of truth)
             ├─ .env (admin-managed, not in git)
             ├─ docker-compose.yml + docker-compose.prod.yml
             └─ docker stack: frontend | backend | db | redis | qdrant | neo4j
```

## 4. Trigger Rules

| Event                | Job `test` | Job `deploy` |
|----------------------|------------|--------------|
| Push to `main`       | yes        | yes          |
| PR targeting `main`  | yes        | no           |
| Push to other branch | no         | no           |

## 5. Components

### 5.1 GitHub Actions Workflow

File: `.github/workflows/ci-cd.yml`

**Job `test`:**
- Runner: `ubuntu-latest`
- Service containers:
  - `postgres:15-alpine` — exposes 5432, env `POSTGRES_USER/PASSWORD/DB` set for tests
  - `redis:7-alpine` — exposes 6379
- Steps:
  1. `actions/checkout@v4`
  2. `actions/setup-python@v5` with Python 3.10 + pip cache
  3. Install system deps (if any, e.g., `libpq-dev` for asyncpg)
  4. `pip install -r server/requirements.txt`
  5. Run `pytest server/tests/` with env vars pointing at service containers
  6. `actions/setup-node@v4` with Node 18 + npm cache
  7. `npm ci`
  8. `npm run build` — fails if Vite build fails

**Job `deploy`:**
- Runner: `ubuntu-latest`
- `needs: test`
- `if: github.event_name == 'push' && github.ref == 'refs/heads/main'`
- Uses `appleboy/ssh-action@v1` (widely used, maintained)
- Secrets consumed: `SSH_HOST`, `SSH_USER`, `SSH_PORT`, `SSH_PRIVATE_KEY`
- Remote script:
  ```bash
  set -e
  cd /opt/deepmory
  git fetch origin main
  git reset --hard origin/main
  docker compose -f docker-compose.yml -f docker-compose.prod.yml pull || true
  docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d --build
  docker image prune -f
  ```
- `set -e` ensures failure at any step aborts the deploy with non-zero exit.

### 5.2 Docker Compose Production Override

File: `docker-compose.prod.yml`

- `restart: always` on all services
- Remove public port bindings on `db`, `redis`, `qdrant`, `neo4j` (internal network only)
- Remove `redis-commander` service entirely (dev tool)
- Add `logging:` limits (JSON file driver, max-size 10m, max-file 3)
- Optional: pin image tags to specific versions instead of `latest`

Used via: `docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d`

### 5.3 Dockerfile Improvements

**Backend (`server/Dockerfile`):** convert to multi-stage
- Stage 1 (`builder`): `python:3.10-slim`, install build-essential, compile wheels into `/wheels`
- Stage 2 (runtime): `python:3.10-slim`, copy wheels, `pip install --no-index --find-links=/wheels`
- Add `HEALTHCHECK` calling `curl -f http://localhost:3000/api/v1/health || exit 1`
- Install only `curl` in runtime stage for health check

**Frontend (`Dockerfile`):** already multi-stage, add `HEALTHCHECK` calling `wget --spider http://localhost/ || exit 1`

### 5.4 Dockerignore Files

File `.dockerignore` (root) — excludes from frontend build context:
- `node_modules/`, `dist/`, `.git/`, `.env*`, `server/`, `docs/`, `*.md` (except what's needed)

File `server/.dockerignore` — excludes from backend build context:
- `__pycache__/`, `*.pyc`, `.pytest_cache/`, `tests/`, `.venv/`, `data/`, `.env*`

Reduces image build time and size.

### 5.5 Health Check Endpoint

Add `GET /api/v1/health` to backend. Returns 200 if service up; includes component status:

```json
{
  "status": "ok",
  "timestamp": "2026-04-13T10:00:00Z",
  "db": "ok",
  "redis": "ok"
}
```

Implementation: new file `server/modules/system/router.py` (new module following existing pattern) OR a simple route added in `server/main.py`. Use whichever is least invasive — leaning toward the router module to match project conventions.

DB check: `SELECT 1` via existing pool. Redis check: `PING`. If either fails, return 503 with degraded status so Docker marks the container unhealthy.

### 5.6 Deploy Scripts + Docs

Directory: `deploy/`

- `deploy/bootstrap.sh` — run **once** on the server by admin:
  - Check prerequisites (docker, docker compose, git installed)
  - Clone repo to `/opt/deepmory` if empty
  - Copy `.env.example` → `.env` and `server/.env.example` → `server/.env`
  - Print next steps (edit .env files, add GitHub deploy key, etc.)
- `deploy/README.md` — admin-facing documentation:
  - Initial server setup (create `deploy` user, SSH keys, firewall, install docker)
  - GitHub Actions secrets to configure
  - Env vars explanation
  - Rotate secrets procedure
  - Rollback procedure (`git reset --hard <commit>` + `docker compose up -d --build`)
  - Troubleshooting (common failures: workflow logs, `docker compose logs`, health endpoint)

## 6. Secrets Management

**Server-side (manual, admin-managed):**
- `/opt/deepmory/.env` — frontend env vars
- `/opt/deepmory/server/.env` — backend env vars (DB password, API keys, SECRET_KEY, etc.)
- Permissions: `chmod 600`, owned by `deploy` user

**GitHub Secrets (repo-level):**
- `SSH_HOST` — server IP or domain
- `SSH_USER` — `deploy`
- `SSH_PORT` — `22` (or custom)
- `SSH_PRIVATE_KEY` — full private key content (including BEGIN/END lines)

**GitHub Actions never reads or modifies `.env` files on the server.** Changing secrets = SSH in manually, edit `.env`, restart stack.

## 7. Server Setup Requirements

Prerequisites on VPS (documented in `deploy/README.md`):
1. Ubuntu 22.04 LTS (or similar)
2. Docker Engine + Docker Compose v2 installed
3. `git` installed
4. Non-root user `deploy`, added to `docker` group
5. SSH access for `deploy` user using key from GitHub Actions
6. GitHub deploy key configured (for private repo `git pull`)
7. `/opt/deepmory` owned by `deploy`
8. Firewall: allow 22 (SSH), 80 (HTTP), 443 (HTTPS if using). Block 3000, 5432, 6379, 6333, 7474, 7687.
9. (Recommended) `fail2ban` installed, `sshd` configured with `PasswordAuthentication no` and `PermitRootLogin no`

## 8. Rollback Procedure

Manual, documented in `deploy/README.md`:

```bash
ssh deploy@<SERVER>
cd /opt/deepmory
git log --oneline -10              # find last known-good commit
git reset --hard <commit-hash>
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d --build
docker compose logs -f backend     # verify
```

If `.env` schema changed in the new version, admin may need to adjust `.env` before restart.

## 9. Testing Strategy

**CI tests (run on every push/PR):**
- `pytest server/tests/` — backend unit + integration tests against real Postgres + Redis service containers
- `npm run build` — frontend build smoke test (Vite compiles, no type errors for TS if any)

**Deployment smoke test (post-deploy):**
- Optional: workflow step to `curl` the `/api/v1/health` endpoint from the runner after deploy, fail the job if not 200 within 60s. This provides automatic verification that deploy succeeded without needing rollback automation.

## 10. Error Handling

- `set -e` in remote deploy script ensures fail-fast
- Workflow job fails → GitHub shows red X → team notified via standard GitHub notifications
- Docker health checks cause unhealthy containers to show in `docker compose ps` (no auto-restart of broken app containers beyond normal restart policy)
- Logs accessible via `docker compose logs <service>` on server

## 11. Files Created / Modified

**Created:**
- `.github/workflows/ci-cd.yml`
- `docker-compose.prod.yml`
- `.dockerignore`
- `server/.dockerignore`
- `deploy/bootstrap.sh`
- `deploy/README.md`
- `server/modules/system/router.py` (health endpoint, if following module pattern)
- `server/modules/system/service.py` (health logic)

**Modified:**
- `server/Dockerfile` — multi-stage + HEALTHCHECK + curl
- `Dockerfile` — add HEALTHCHECK
- `docker-compose.yml` — add healthchecks to backend/frontend/db/redis
- `server/main.py` — wire up system router (or add health route directly)
- `server/apiRouter.py` — include system router

## 12. User-Provided Prerequisites Before Deploy Works

The user must provide/configure before first deploy:
1. A VPS with Docker installed and SSH access
2. A `deploy` user on the server (bootstrap script will help)
3. `.env` files populated on server at `/opt/deepmory/.env` and `/opt/deepmory/server/.env`
4. 4 GitHub Secrets set: `SSH_HOST`, `SSH_USER`, `SSH_PORT`, `SSH_PRIVATE_KEY`
5. GitHub deploy key added to repo (if private) and configured on server

The implementation phase produces all code + docs; the user runs the documented one-time server setup.

## 13. Open Questions / Assumptions

- **Assumption:** backend tests in `server/tests/` can run with a fresh Postgres + Redis (no seed data needed). If tests require migrations, CI will run them before pytest.
- **Assumption:** repo will be private on GitHub — deploy key setup documented. If public, instructions simplified.
- **Assumption:** there is no existing production deployment to migrate from — this is green-field CI/CD setup.
- **Assumption:** SSL/HTTPS termination is out of scope for this spec. User can add Caddy/Traefik/Nginx reverse proxy later; nothing here blocks that.

---

**End of spec.**
