FROM prefecthq/prefect:3-latest

# Install Cloud SQL Proxy
RUN wget https://storage.googleapis.com/cloud-sql-connectors/cloud-sql-proxy/v2.6.1/cloud-sql-proxy.linux.amd64 -O /usr/local/bin/cloud-sql-proxy && \
    chmod +x /usr/local/bin/cloud-sql-proxy

# Install required packages
RUN pip install prefect-gcp psycopg2-binary asyncpg

# Copy startup script
COPY start-server.sh /app/start-server.sh
RUN chmod +x /app/start-server.sh

# Start Prefect server
ENTRYPOINT ["/app/start-server.sh"]