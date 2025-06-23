#!/bin/bash

# Exit on error
set -e

# Check if required environment variables are set
if [ -z "$GOOGLE_CLOUD_PROJECT" ]; then
    echo "Error: GOOGLE_CLOUD_PROJECT environment variable is required"
    exit 1
fi

# Set variables
DATASET_ID="userport_enrichment"
LOCATION="US"

echo "Creating BigQuery dataset and tables for project: $GOOGLE_CLOUD_PROJECT"

# Create the dataset if it doesn't exist
bq mk --dataset \
    --description "Dataset for storing enrichment data" \
    --location=$LOCATION \
    "$GOOGLE_CLOUD_PROJECT:$DATASET_ID"

# Create account_data table
bq mk \
    --table \
    --schema './schemas/account_data_schema.json' \
    "$GOOGLE_CLOUD_PROJECT:$DATASET_ID.account_data"

# Create enrichment_raw_data table
bq mk \
    --table \
    --schema './schemas/enrichment_raw_data_schema.json' \
    "$GOOGLE_CLOUD_PROJECT:$DATASET_ID.enrichment_raw_data"

echo "BigQuery setup completed successfully!"