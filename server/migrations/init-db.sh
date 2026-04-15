#!/bin/bash
set -e

echo "==> Running DeepMory database initialization..."

psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" -f /docker-entrypoint-initdb.d/init.sql

echo "==> Database initialized successfully."
