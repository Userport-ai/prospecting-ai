#!/bin/bash

# Start Cloud SQL Proxy in the background
cloud-sql-proxy --port=5432 \
    omega-winter-431704-u5:us-central1:userport-pg \
    --credentials-file=/secrets/service-account.json &

# Wait for the proxy to start
sleep 5

# Calculate workers if not set (2 * CPU cores + 1)
if [ -z "${GUNICORN_WORKERS}" ]; then
    GUNICORN_WORKERS=$((2 * $(nproc) + 1))
fi

# Use environment variables with defaults
GUNICORN_TIMEOUT="${GUNICORN_TIMEOUT:-120}"
GUNICORN_PORT="${PORT:-8000}"

# Start Gunicorn
exec gunicorn \
    --bind "0.0.0.0:${GUNICORN_PORT}" \
    --timeout "${GUNICORN_TIMEOUT}" \
    --workers "${GUNICORN_WORKERS}" \
    userport.wsgi:application