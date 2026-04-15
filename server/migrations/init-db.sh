#!/bin/bash
set -e

DB_TEST="${POSTGRES_DB}_test"

echo "==> Initializing main database: $POSTGRES_DB ..."
psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" \
  -f /docker-entrypoint-initdb.d/init.sql

echo "==> Creating test database: $DB_TEST ..."
psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "postgres" <<SQL
SELECT 'CREATE DATABASE "$DB_TEST" OWNER "$POSTGRES_USER"'
WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = '$DB_TEST')\gexec
SQL

echo "==> Initializing test database schema ..."
psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$DB_TEST" \
  -f /docker-entrypoint-initdb.d/init.sql

echo "==> All databases initialized successfully."
