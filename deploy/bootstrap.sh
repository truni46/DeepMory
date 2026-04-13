#!/usr/bin/env bash
# One-time server setup for DeepMory.
# Run as the `deploy` user on a fresh VPS.

set -euo pipefail

APP_DIR="/opt/deepmory"
REPO_URL="${REPO_URL:-git@github.com:YOUR_ORG/YOUR_REPO.git}"

echo "=== DeepMory server bootstrap ==="

command -v git >/dev/null 2>&1 || { echo "ERROR: git not installed"; exit 1; }
command -v docker >/dev/null 2>&1 || { echo "ERROR: docker not installed"; exit 1; }
docker compose version >/dev/null 2>&1 || { echo "ERROR: docker compose v2 not installed"; exit 1; }

if [ ! -d "$APP_DIR" ]; then
  echo "ERROR: $APP_DIR does not exist. Create it as root: sudo mkdir -p $APP_DIR && sudo chown $USER:$USER $APP_DIR"
  exit 1
fi

cd "$APP_DIR"

if [ ! -d "$APP_DIR/.git" ]; then
  echo "Cloning repo..."
  echo "Make sure your GitHub deploy key is configured in ~/.ssh/ and added to the repo."
  git clone "$REPO_URL" .
else
  echo "Repo already cloned."
fi

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
