#!/bin/bash

# TechLens Backend Deployment Script
# Usage: ./deploy.sh [--project PROJECT_ID] [--region REGION]
#
# Example:
#   ./deploy.sh --project techlens-490020 --region us-central1
#   ./deploy.sh  # Uses default gcloud project

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
echo "Project:  $PROJECT_ID"
echo "Region:   $REGION"
echo "Service:  $SERVICE_NAME"
echo "Image:    gcr.io/$PROJECT_ID/$IMAGE_NAME"
echo ""

# Build from project root (Dockerfile needs backend/ + test_knowledgebase/)
echo "Building Docker image via Cloud Build..."
gcloud builds submit \
  --config cloudbuild.yaml \
  --project "$PROJECT_ID" \
  .

echo ""
echo "Deploying to Cloud Run..."
gcloud run deploy "$SERVICE_NAME" \
  --image "gcr.io/$PROJECT_ID/$IMAGE_NAME" \
  --platform managed \
  --region "$REGION" \
  --allow-unauthenticated \
  --port 8080 \
  --memory 512Mi \
  --timeout 300 \
  --set-env-vars "GOOGLE_API_KEY=$(grep GOOGLE_API_KEY backend/.env | cut -d= -f2)" \
  --project "$PROJECT_ID"

echo ""
SERVICE_URL=$(gcloud run services describe "$SERVICE_NAME" --region "$REGION" --project "$PROJECT_ID" --format 'value(status.url)' 2>/dev/null)
echo "Deployment successful!"
echo "Service URL: $SERVICE_URL"
echo ""
echo "Verify: curl $SERVICE_URL/health"
echo "Logs:   gcloud run logs read $SERVICE_NAME --region $REGION --project $PROJECT_ID"
