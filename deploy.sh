#!/bin/bash
set -e

COMPOSE="docker compose -f docker-compose.yml -f docker-compose.prod.yml"

buildFrontend() {
  echo "Building frontend dist..."
  docker run --rm \
    -v "$(pwd):/app" \
    -v deepmory_node_modules:/app/node_modules \
    -w /app \
    -e VITE_API_URL=/api/v1 \
    -e VITE_SOCKET_URL= \
    node:18-alpine sh -c "npm install && npm run build"
}

echo "Pulling latest code..."
git pull

PREV=$(git rev-parse HEAD@{1} 2>/dev/null || echo "")
CURR=$(git rev-parse HEAD)

if [ -z "$PREV" ] || [ "$PREV" = "$CURR" ]; then
  echo "No new commits. Restarting services..."
  [ ! -d dist ] && buildFrontend
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

# Nginx image: only rebuild if nginx.Dockerfile changed (very rare)
if echo "$CHANGED" | grep -qE "^nginx\.Dockerfile"; then
  echo "Nginx Dockerfile changed → rebuilding frontend image..."
  BUILD_ARGS="$BUILD_ARGS frontend"
fi

if [ -n "$BUILD_ARGS" ]; then
  $COMPOSE build $BUILD_ARGS
fi

# Frontend: build dist if code/config/deps changed, or dist/ missing
if [ ! -d dist ] || echo "$CHANGED" | grep -qE "^(package.*\.json|src/|index\.html|vite\.config|public/|tailwind\.config)"; then
  buildFrontend
fi

$COMPOSE up -d
echo "Deploy done."
