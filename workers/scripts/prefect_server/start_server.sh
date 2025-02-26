#!/bin/bash
set -e

# Enable debug logging
echo "Starting Cloud SQL Proxy..."

# Start Cloud SQL Proxy in the background with verbose logging
cloud-sql-proxy --address 0.0.0.0 --port 5432 omega-winter-431704-u5:us-east1:prefect-db --log-level=debug &
PROXY_PID=$!

# Wait for proxy to start
echo "Waiting for Cloud SQL Proxy to start..."
sleep 5

# Check if proxy is running
if ps -p $PROXY_PID > /dev/null; then
  echo "Cloud SQL Proxy is running with PID $PROXY_PID"
else
  echo "ERROR: Cloud SQL Proxy failed to start"
fi

# Get password from environment variable
DB_PASSWORD=${PREFECT_DB_PASSWORD}
if [ -z "$DB_PASSWORD" ]; then
  echo "ERROR: PREFECT_DB_PASSWORD environment variable is not set"
  exit 1
fi

echo "Password length: ${#DB_PASSWORD} characters"

# Test PostgreSQL connection directly
echo "Testing PostgreSQL connection..."
PGPASSWORD=$DB_PASSWORD psql -h localhost -p 5432 -U prefect -d prefect -c "SELECT 1" || echo "Connection test failed"

# Try both TCP and socket connection options
# Option 1: TCP connection (original)
export PREFECT_API_DATABASE_CONNECTION_URL="postgresql+asyncpg://prefect:${DB_PASSWORD}@localhost:5432/prefect"
echo "Connection URL set (TCP, password masked): postgresql+asyncpg://prefect:****@localhost:5432/prefect"

# Option 2: Try socket connection as fallback if TCP fails
# export PREFECT_API_DATABASE_CONNECTION_URL="postgresql+asyncpg://prefect:${DB_PASSWORD}@/prefect?host=/cloudsql/omega-winter-431704-u5:us-east1:prefect-db"
# echo "Connection URL set (socket, password masked): postgresql+asyncpg://prefect:****@/prefect?host=/cloudsql/omega-winter-431704-u5:us-east1:prefect-db"

# Use PORT environment variable provided by Cloud Run, default to 8080 if not set
PORT=${PORT:-8080}

# Start Prefect server
prefect server start --host 0.0.0.0 --port "${PORT}"