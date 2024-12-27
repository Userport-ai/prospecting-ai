# syntax=docker/dockerfile:1
FROM python:3.10

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
    PORT=$PORT \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    STATIC_ROOT=/app/staticfiles

WORKDIR /app

# Install system dependencies and create static files directory
RUN apt-get update && apt-get install -y \
    gcc \
    wget \
    netcat-traditional && \
    rm -rf /var/lib/apt/lists/* && \
    mkdir -p /app/staticfiles

# Install cloud-sql-proxy, defaulting to amd64 if architecture isn't specified
RUN ARCH=$(uname -m); \
    if [ "$ARCH" = "aarch64" ]; then \
        CLOUD_SQL_PROXY_ARCH="arm64"; \
    else \
        CLOUD_SQL_PROXY_ARCH="amd64"; \
    fi && \
    wget https://storage.googleapis.com/cloud-sql-connectors/cloud-sql-proxy/v2.8.1/cloud-sql-proxy.linux.${CLOUD_SQL_PROXY_ARCH} -O /usr/local/bin/cloud-sql-proxy && \
    chmod +x /usr/local/bin/cloud-sql-proxy

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt && \
    pip install gunicorn

# Copy the django app
COPY . .

RUN chmod +x start.sh && \
    python manage.py collectstatic --noinput

ENV USERPORT_DEBUG=0

CMD ["/bin/bash", "./start.sh"]