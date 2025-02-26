#!/bin/bash
set -e

# Enable debug logging
echo "Starting Cloud SQL Proxy..."

# Start Cloud SQL Proxy in the background - using flags supported by this version
cloud-sql-proxy --address 0.0.0.0 --port 5432 omega-winter-431704-u5:us-east1:prefect-db &

# Wait longer for proxy to start
echo "Waiting for Cloud SQL Proxy to start..."
sleep 10

# Verify if proxy is listening on port
if nc -z localhost 5432; then
  echo "Cloud SQL Proxy is running and listening on port 5432"
else
  echo "ERROR: Cloud SQL Proxy failed to start or is not listening on port 5432"
fi

# Get password from environment variable
DB_PASSWORD=${PREFECT_DB_PASSWORD}
if [ -z "$DB_PASSWORD" ]; then
  echo "ERROR: PREFECT_DB_PASSWORD environment variable is not set"
  exit 1
fi

echo "Password length: ${#DB_PASSWORD} characters"

# If proxy is listening, use TCP connection; otherwise use socket connection
if nc -z localhost 5432; then
  # Option 1: TCP connection (original)
  export PREFECT_API_DATABASE_CONNECTION_URL="postgresql+asyncpg://prefect:${DB_PASSWORD}@localhost:5432/prefect"
  echo "Using TCP connection URL (password masked): postgresql+asyncpg://prefect:****@localhost:5432/prefect"
  
  # Test with psql
  echo "Testing PostgreSQL TCP connection..."
  PGPASSWORD="$DB_PASSWORD" psql -h localhost -p 5432 -U prefect -d prefect -c "SELECT 1" || echo "TCP connection test failed"
else
  # Option 2: Try socket connection as fallback if TCP fails
  mkdir -p /cloudsql
  # Start Cloud SQL Proxy with Unix socket instead
  cloud-sql-proxy --unix-socket /cloudsql omega-winter-431704-u5:us-east1:prefect-db &
  sleep 5
  
  export PREFECT_API_DATABASE_CONNECTION_URL="postgresql+asyncpg://prefect:${DB_PASSWORD}@/prefect?host=/cloudsql/omega-winter-431704-u5:us-east1:prefect-db"
  echo "Using socket connection URL (password masked): postgresql+asyncpg://prefect:****@/prefect?host=/cloudsql/omega-winter-431704-u5:us-east1:prefect-db"
  
  # Test with psql
  echo "Testing PostgreSQL socket connection..."
  PGPASSWORD="$DB_PASSWORD" psql "host=/cloudsql/omega-winter-431704-u5:us-east1:prefect-db user=prefect dbname=prefect" -c "SELECT 1" || echo "Socket connection test failed"
fi

# Use PORT environment variable provided by Cloud Run, default to 8080 if not set
PORT=${PORT:-8080}

# Start Prefect server
prefect server start --host 0.0.0.0 --port "${PORT}"