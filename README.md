# TechLens

**AI-powered voice and video diagnosis for technical support and device troubleshooting.**

## Problem Statement

Tech support documentation is fragmented, outdated, and often inaccessible to users who need it most. TechLens bridges this gap by enabling users to describe their device or software issues verbally and visually, receiving instant, AI-powered diagnostic insights without navigating complex knowledge bases.

## Features

- **Voice + Camera Diagnosis**: Describe issues in natural language while showing your device via camera for real-time AI analysis
- **Technical Support Lookup**: Instantly retrieve relevant technical support bulletins and troubleshooting guides
- **3 Auto-Generated Outputs**: Diagnosis summary, step-by-step fixes, and escalation recommendations

## Architecture

TechLens uses a multi-tier architecture:

1. **Frontend (React + Vite)**: Real-time voice capture and camera streaming UI
2. **Backend (FastAPI on Cloud Run)**: Orchestrates API calls and manages diagnostic workflows
3. **Gemini Live API**: Processes real-time voice/video streams with agentic capabilities
4. **Firestore**: Stores diagnostic history and support bulletins for TSB lookup

Data flows from the frontend through secure WebSocket connections to the backend, which streams audio/video to Gemini Live API. The AI agent performs TSB lookups, generates diagnostics, and returns structured recommendations back to the frontend.

## Tech Stack

- **Frontend**: React, Vite, Tailwind CSS, JavaScript
- **Backend**: FastAPI, Python 3.12, uvicorn
- **AI/ML**: Google Gemini Live API, Google Generative AI SDK
- **Cloud**: Google Cloud Run, Cloud Build, Firestore
- **Communication**: WebSockets

## Quick Start

### Prerequisites
- Python 3.12+ (backend)
- Node.js 18+ (frontend)
- Google Cloud SDK (`gcloud` CLI)
- GCP project with Firestore and Generative AI APIs enabled

### Local Development

**Backend:**
```bash
cd backend
pip install -r requirements.txt
uvicorn main:app --reload --port 8080
```

The backend will be available at `http://localhost:8080`

**Frontend:**
```bash
cd frontend
npm install
npm run dev
```

The frontend will be available at `http://localhost:5173`

## Deployment

Deploy the backend to Google Cloud Run using the provided deployment script:

```bash
./deploy.sh --project YOUR_GCP_PROJECT_ID --region us-central1
```

The script will:
1. Build a Docker image using Cloud Build
2. Push the image to Google Container Registry
3. Deploy to Cloud Run with public, unauthenticated access
4. Output the service URL on success

For usage details: `./deploy.sh --help` or see [deploy.sh](./deploy.sh)

## Environment Variables

Backend requires:
- `GOOGLE_API_KEY`: Google Generative AI API key
- `GOOGLE_APPLICATION_CREDENTIALS`: Path to GCP service account JSON (for Firestore)
- `FIRESTORE_PROJECT_ID`: GCP project ID (optional, auto-detected from credentials)

See `.env.example` or `backend/main.py` for configuration details.

## Contest

TechLens is built for the **Gemini Live Agent Challenge** by **Adair Labs**.

This project demonstrates agentic AI workflows using Google's latest multimodal capabilities to solve real-world technical support challenges.

## License

MIT
