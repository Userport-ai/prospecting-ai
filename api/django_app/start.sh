#!/bin/bash

# Check if we're running locally (using service account JSON) or in GKE (using Workload Identity)
if [ -f "/secrets/service-account.json" ]; then
    # Local development with service account JSON
    cloud-sql-proxy --port=5432 \
        "omega-winter-431704-u5:us-central1:userport-pg" \
        --credentials-file=/secrets/service-account.json &
else
    # Production with Workload Identity
    cloud-sql-proxy --port=5432 --quiet \
        "omega-winter-431704-u5:us-central1:userport-pg" &
fi

# Wait for the proxy to be ready
echo "Waiting for Cloud SQL Proxy to be ready..."
for i in {1..30}; do
    if nc -z localhost 5432; then
        echo "Cloud SQL Proxy is ready!"
        break
    fi
    if [ $i -eq 30 ]; then
        echo "Cloud SQL Proxy failed to start"
        exit 1
    fi
    echo "Waiting for Cloud SQL Proxy... ($i/30)"
    sleep 2
done

# Calculate workers if not set
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
    --log-level info \
    userport.wsgi:application