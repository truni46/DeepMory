#!/bin/bash
set -e

COMPOSE="docker compose -f docker-compose.yml -f docker-compose.prod.yml"

echo "Pulling latest code..."
git pull

PREV=$(git rev-parse HEAD@{1} 2>/dev/null || echo "")
CURR=$(git rev-parse HEAD)

if [ -z "$PREV" ] || [ "$PREV" = "$CURR" ]; then
  echo "No new commits. Restarting services..."
  $COMPOSE up -d
  exit 0
fi

CHANGED=$(git diff "$PREV" "$CURR" --name-only)
echo "Changed files:"
echo "$CHANGED"

BUILD_ARGS=""

# Backend: only rebuild if Dockerfile or requirements.txt changed
# Source code is volume-mounted — restart is enough for .py changes
if echo "$CHANGED" | grep -qE "^server/(Dockerfile|requirements\.txt)"; then
  echo "Backend deps changed → rebuilding backend image..."
  BUILD_ARGS="$BUILD_ARGS backend"
fi

# Frontend: rebuild if Dockerfile, nginx.conf, src/, or package*.json changed
if echo "$CHANGED" | grep -qE "^(Dockerfile|nginx\.conf|package.*\.json|src/|index\.html|vite\.config)"; then
  echo "Frontend changed → rebuilding frontend image..."
  BUILD_ARGS="$BUILD_ARGS frontend"
fi

if [ -n "$BUILD_ARGS" ]; then
  $COMPOSE build $BUILD_ARGS
fi

$COMPOSE up -d
echo "Deploy done."
