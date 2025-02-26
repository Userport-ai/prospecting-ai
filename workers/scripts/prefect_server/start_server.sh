#!/bin/bash
set -e

# Start Cloud SQL Proxy in the background
cloud-sql-proxy --address 0.0.0.0 --port 5432 omega-winter-431704-u5:us-central1:prefect-db &

# Wait for proxy to start
sleep 5

# Get password from environment variable
DB_PASSWORD=${PREFECT_DB_PASSWORD}

# Set environment variables for database connection
export PREFECT_API_DATABASE_CONNECTION_URL="postgresql+asyncpg://prefect:${DB_PASSWORD}@localhost:5432/prefect"

# Use PORT environment variable provided by Cloud Run, default to 8080 if not set
PORT=${PORT:-8080}

# Start Prefect server
prefect server start --host 0.0.0.0 --port "${PORT}"