#!/bin/bash
set -e

# Set project ID
PROJECT_ID="omega-winter-431704-u5"
SERVICE_NAME="prefect-server"
REGION="us-east1"
SERVICE_URL="https://prefect-server-116199002084.us-east1.run.app"

# Create the service account for IAP
echo "Creating IAP service account..."
gcloud iam service-accounts create iap-prefect-sa \
  --display-name="IAP Prefect Service Account" \
  --project="${PROJECT_ID}"

# Wait for service account creation to propagate
sleep 10

# Get the service account email
SA_EMAIL="iap-prefect-sa@${PROJECT_ID}.iam.gserviceaccount.com"
echo "Service account created: ${SA_EMAIL}"

# Grant the service account the IAP-secured Web App User role
echo "Granting IAP-secured Web App User role..."
gcloud projects add-iam-policy-binding "${PROJECT_ID}" \
  --member="serviceAccount:${SA_EMAIL}" \
  --role="roles/iap.httpsResourceAccessor"

# Configure the OAuth consent screen (internal only)
echo "Setting up OAuth consent screen..."
cat > consent_screen.json <<EOF
{
  "support_email": "sowrabh@userport.ai",
  "application_title": "Prefect Server IAP",
  "application_type": "INTERNAL"
}
EOF

gcloud iap oauth-brands create \
  --application_title="Prefect Server IAP" \
  --support_email="sowrabh@userport.ai"

# Create OAuth client
echo "Creating OAuth client..."
BRAND=$(gcloud iap oauth-brands list --format="value(name)" --limit=1)

# Create the OAuth client for IAP
CLIENT_INFO=$(gcloud iap oauth-clients create "${BRAND}" \
  --display_name="Prefect Server IAP Client" \
  --format="json")

# Extract client ID and secret
CLIENT_ID=$(echo "${CLIENT_INFO}" | grep -o '"clientId": "[^"]*' | cut -d'"' -f4)
CLIENT_SECRET=$(echo "${CLIENT_INFO}" | grep -o '"clientSecret": "[^"]*' | cut -d'"' -f4)

echo "OAuth client created with ID: ${CLIENT_ID}"

# Update Cloud Run service to use IAP
echo "Configuring Cloud Run service for IAP..."
gcloud run services update "${SERVICE_NAME}" \
  --region="${REGION}" \
  --ingress=internal-and-cloud-load-balancing

# Create IAP settings
echo "Creating IAP settings for the Cloud Run service..."
gcloud iap web create \
  --resource-type=CLOUD_RUN \
  --service="${SERVICE_NAME}" \
  --region="${REGION}" \
  --oauth2-client-id="${CLIENT_ID}" \
  --oauth2-client-secret="${CLIENT_SECRET}"

# Set IAP access policy
echo "Setting IAP access policy..."
gcloud iap web add-iam-policy-binding \
  --resource-type=CLOUD_RUN \
  --service="${SERVICE_NAME}" \
  --region="${REGION}" \
  --member="domain:userport.ai" \
  --role="roles/iap.httpsResourceAccessor"

# Also add the specific user
gcloud iap web add-iam-policy-binding \
  --resource-type=CLOUD_RUN \
  --service="${SERVICE_NAME}" \
  --region="${REGION}" \
  --member="user:sowrabh@userport.ai" \
  --role="roles/iap.httpsResourceAccessor"

echo "IAP setup completed successfully!"
echo "The Prefect Server is now protected by IAP and accessible at: ${SERVICE_URL}"
echo "Only authenticated users from userport.ai domain and sowrabh@userport.ai can access it."