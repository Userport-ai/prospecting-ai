# syntax=docker/dockerfile:1

# ---- Base Python ----
FROM python:3.10-slim AS python-base
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=0 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    STATIC_ROOT=/app/staticfiles

# ---- Dependencies ----
FROM python-base AS builder

WORKDIR /wheels

# Copy requirements files
COPY requirements.txt .

# Install build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Build wheels with pip cache
RUN --mount=type=cache,target=/root/.cache/pip \
    pip wheel --wheel-dir=/wheels \
    --requirement requirements.txt \
    --wheel-dir=/wheels \
    gunicorn \
    && pip wheel asgiref>=3.8.1

# ---- Final stage ----
FROM python-base
WORKDIR /app

# Runtime args
ARG USERPORT_DEBUG
ARG USERPORT_DEV_DB_USERNAME
ARG USERPORT_DEV_DB_PASSWORD
ARG ALLOWED_HOSTS
ARG GUNICORN_WORKERS
ARG GUNICORN_TIMEOUT
ARG PORT

# Set environment variables
ENV USERPORT_DEBUG=$USERPORT_DEBUG \
    USERPORT_DEV_DB_USERNAME=$USERPORT_DEV_DB_USERNAME \
    USERPORT_DEV_DB_PASSWORD=$USERPORT_DEV_DB_PASSWORD \
    ALLOWED_HOSTS=$ALLOWED_HOSTS \
    GUNICORN_WORKERS=$GUNICORN_WORKERS \
    GUNICORN_TIMEOUT=$GUNICORN_TIMEOUT \
    PORT=$PORT

# Create directories and install ALL runtime dependencies in one layer
RUN mkdir -p /app/staticfiles && \
    apt-get update && apt-get install -y --no-install-recommends \
    wget \
    netcat-traditional \
    && rm -rf /var/lib/apt/lists/* && \
    # Install cloud-sql-proxy based on the architecture
    ARCH=$(uname -m) && \
    if [ "$ARCH" = "aarch64" ]; then \
        CLOUD_SQL_PROXY_ARCH="arm64"; \
    else \
        CLOUD_SQL_PROXY_ARCH="amd64"; \
    fi && \
    wget https://storage.googleapis.com/cloud-sql-connectors/cloud-sql-proxy/v2.8.1/cloud-sql-proxy.linux.${CLOUD_SQL_PROXY_ARCH} -O /usr/local/bin/cloud-sql-proxy && \
    chmod +x /usr/local/bin/cloud-sql-proxy

# Copy wheels from builder stage
COPY --from=builder /wheels /wheels
COPY requirements.txt .

RUN --mount=type=cache,target=/root/.cache/pip \
    pip install --no-index --find-links=/wheels -r requirements.txt \
    && pip install --no-index --find-links=/wheels gunicorn \
    && rm -rf /wheels

# Copy application code
COPY . .

# Collect static files
# RUN chmod +x start.sh && \
#     python manage.py collectstatic --noinput
RUN chmod +x start.sh

ENV USERPORT_DEBUG=0

CMD ["/bin/bash", "./start.sh"]