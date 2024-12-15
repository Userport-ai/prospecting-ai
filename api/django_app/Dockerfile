FROM python:3.10-slim

# Set basic Python environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    STATIC_ROOT=/app/staticfiles

WORKDIR /app

# Install system dependencies, create static files directory, and install cloud-sql-proxy
RUN apt-get update && apt-get install -y \
    gcc \
    wget && \
    rm -rf /var/lib/apt/lists/* && \
    mkdir -p /app/staticfiles && \
    wget https://storage.googleapis.com/cloud-sql-connectors/cloud-sql-proxy/v2.8.1/cloud-sql-proxy.linux.arm64 -O /usr/local/bin/cloud-sql-proxy && \
    chmod +x /usr/local/bin/cloud-sql-proxy

# Rest of your Dockerfile remains the same
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt && \
    pip install gunicorn

COPY . .

RUN chmod +x start.sh && \
    python manage.py collectstatic --noinput

ENV DEBUG=0

CMD ["/bin/bash", "./start.sh"]