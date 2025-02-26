FROM prefecthq/prefect:2.11.5-python3.11

# Install required system packages
RUN apt-get update && apt-get install -y wget postgresql-client netcat-openbsd procps

# Install Cloud SQL Proxy
RUN wget https://storage.googleapis.com/cloud-sql-connectors/cloud-sql-proxy/v2.6.1/cloud-sql-proxy.linux.amd64 -O /usr/local/bin/cloud-sql-proxy && \
    chmod +x /usr/local/bin/cloud-sql-proxy

# Install required packages
RUN pip install prefect-gcp psycopg2-binary asyncpg

# Copy startup script
COPY workers/scripts/prefect_server/start_server.sh /app/start_server.sh
RUN chmod +x /app/start_server.sh

# Start Prefect server
ENTRYPOINT ["/app/start_server.sh"]