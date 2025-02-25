FROM prefecthq/prefect:3-latest

# Install the dependencies your workflows need
RUN pip install prefect-gcp httpx google-cloud-bigquery google-cloud-tasks

# Install required Userport packages
# (adjust based on what your workflows need)
COPY ../../requirements.txt /app/requirements.txt
RUN pip install -r /app/requirements.txt

# Copy startup script
COPY start-agent.sh /app/start-agent.sh
RUN chmod +x /app/start-agent.sh

# Set environment variables
ENV PREFECT_API_URL=https://YOUR_PREFECT_SERVER_URL

# Start the agent
ENTRYPOINT ["/app/start-agent.sh"]