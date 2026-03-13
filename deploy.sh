#!/bin/bash

# TechLens Backend Deployment Script
# Usage: ./deploy.sh [--project PROJECT_ID] [--region REGION]
#
# Example:
#   ./deploy.sh --project my-gcp-project --region us-central1
#   ./deploy.sh  # Uses default region (us-central1) - requires GCLOUD_PROJECT env var

set -e

# Configuration
SERVICE_NAME="techlens-backend"
IMAGE_NAME="techlens-backend"
REGION="us-central1"
PROJECT_ID=""

# Parse arguments
while [[ $# -gt 0 ]]; do
  case $1 in
    --project)
      PROJECT_ID="$2"
      shift 2
      ;;
    --region)
      REGION="$2"
      shift 2
      ;;
    *)
      echo "Unknown option: $1"
      echo "Usage: ./deploy.sh [--project PROJECT_ID] [--region REGION]"
      exit 1
      ;;
  esac
done

# If no project specified, try to use gcloud default
if [ -z "$PROJECT_ID" ]; then
  PROJECT_ID=$(gcloud config get-value project 2>/dev/null)
  if [ -z "$PROJECT_ID" ]; then
    echo "Error: GCP project not specified and no default gcloud project set"
    echo "Usage: ./deploy.sh --project YOUR_PROJECT_ID [--region REGION]"
    exit 1
  fi
fi

echo "Deploying TechLens Backend"
echo "=========================="
echo "Project ID: $PROJECT_ID"
echo "Region: $REGION"
echo "Service: $SERVICE_NAME"
echo "Image: gcr.io/$PROJECT_ID/$IMAGE_NAME"
echo ""

# Build Docker image using Cloud Build
echo "Building Docker image..."
gcloud builds submit --tag "gcr.io/$PROJECT_ID/$IMAGE_NAME" backend/ --project "$PROJECT_ID"

if [ $? -ne 0 ]; then
  echo "Error: Failed to build Docker image"
  exit 1
fi

echo ""
echo "Deploying to Cloud Run..."
gcloud run deploy "$SERVICE_NAME" \
  --image "gcr.io/$PROJECT_ID/$IMAGE_NAME" \
  --platform managed \
  --region "$REGION" \
  --allow-unauthenticated \
  --port 8080 \
  --project "$PROJECT_ID"

if [ $? -ne 0 ]; then
  echo "Error: Failed to deploy to Cloud Run"
  exit 1
fi

echo ""
echo "Deployment successful!"
echo "Service URL: https://$SERVICE_NAME-$(echo $REGION | tr '_' '-')-$PROJECT_ID.a.run.app"
echo ""
echo "Tip: To view logs: gcloud run logs read $SERVICE_NAME --region $REGION --project $PROJECT_ID"
