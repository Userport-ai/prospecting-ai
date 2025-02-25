# Create a Cloud SQL PostgreSQL instance for Prefect metadata
gcloud sql instances create prefect-db \
  --database-version=POSTGRES_17 \
  --tier=db-g1-small \
  --region=us-central1 \
  --root-password=YOUR_ROOT_PASSWORD

# Create the Prefect database
gcloud sql databases create prefect --instance=prefect-db

# Create a user for Prefect
gcloud sql users create prefect --instance=prefect-db --password=YOUR_USER_PASSWORD

