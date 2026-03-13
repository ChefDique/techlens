# TechLens

**AI Diagnostic Copilot for Auto Repair Technicians** — Real-time voice + camera diagnosis with automated documentation.

## What It Does

A technician walks up to a car, opens TechLens on their phone, and starts talking. The AI already knows the vehicle's TSBs, known issues, and NHTSA complaint patterns. When they need the AI to look at something — a corroded connector, a torn CV boot — they tap the camera button. TechLens sees it, correlates it with known issues, and guides next steps. When done, three documents are generated automatically: Tech Notes, Customer Summary, and Escalation Brief.

## Architecture — Three-Agent Pipeline

```
SessionStart form → INTAKE AGENT (gemini-2.5-flash) → context package
                         ↓
                    LIVE AGENT (Gemini Live API, bidi-streaming) ← voice + camera
                         ↓
                    WRITER AGENT (gemini-2.5-flash) → Tech Notes, Customer Summary, Escalation Brief
```

### Three-State Session Model

| State | What's happening | Tokens |
|-------|-----------------|--------|
| **IDLE** | WebSocket alive, no streaming | Zero |
| **LISTENING** | Audio streaming to Gemini Live | Audio only |
| **LOOKING** | Audio + video (1 FPS JPEG, 15s auto-stop) | Audio + vision |

### Agent Roles

- **Intake Agent** — Runs once at session start. Queries the 70KB knowledge base for vehicle-specific TSBs, known issues, and NHTSA complaints. Calls Gemini to synthesize a diagnostic context package.
- **Live Agent** — Real-time voice + vision copilot via Gemini Live API (ADK bidi-streaming). System instruction is dynamically injected with Intake context. Has tools for KB search and finding logging.
- **Writer Agent** — Runs once after session ends. Takes the full transcript + findings and generates three polished documents via Gemini.

## Tech Stack

- **Backend:** Python 3.12, FastAPI, Google ADK (`google-adk`), Google GenAI SDK (`google-genai`)
- **Frontend:** React 19, Vite, Tailwind CSS v4
- **AI:** Gemini Live API via ADK (model: `gemini-2.5-flash-native-audio-latest`)
- **Data:** In-memory JSON knowledge base (70KB, 3 Subaru vehicles, 8 TSBs, 175 NHTSA complaints)
- **Deploy:** Cloud Run + Firestore (session persistence)

## Quick Start

### Prerequisites
- Python 3.12+
- Node.js 18+
- Google AI Studio API key

### Backend
```bash
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env  # Add your GOOGLE_API_KEY
uvicorn main:app --reload --port 8080
```

### Frontend
```bash
cd frontend
npm install
npm run dev
```

Open `http://localhost:5173`, fill in vehicle info (2023 Subaru Outback recommended — best KB coverage), and start a session.

## Project Structure

```
techlens/
├── backend/
│   ├── main.py                 # FastAPI WebSocket orchestrator (state machine)
│   ├── agents/
│   │   ├── intake_agent.py     # Pre-filters KB, synthesizes context
│   │   ├── live_agent.py       # Real-time voice+vision ADK agent
│   │   └── writer_agent.py     # Post-session document generation
│   ├── tools/
│   │   ├── knowledge_base.py   # Unified KB search (in-memory JSON)
│   │   ├── vehicle_lookup.py   # Firestore-with-stub vehicle queries
│   │   └── tsb_search.py       # Firestore-with-stub TSB search
│   ├── models/
│   │   └── session_state.py    # SessionPhase enum, IntakeContext, SessionTranscript
│   └── Dockerfile
├── frontend/
│   └── src/
│       ├── App.jsx             # Phase state machine (setup→active→review)
│       ├── components/         # SessionStart, LiveSession, AudioControls, CameraFeed, SessionOutputs
│       └── hooks/              # useWebSocket, useAudioStream, useCameraStream
└── test_knowledgebase/
    └── techlens_knowledge_base.json  # Primary KB (3 vehicles, 14 issues, 8 TSBs)
```

## Environment Variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `GOOGLE_API_KEY` | Yes | — | Google AI Studio API key |
| `TECHLENS_MODEL` | No | `gemini-2.5-flash-native-audio-latest` | Live agent model |
| `TECHLENS_INTAKE_MODEL` | No | `gemini-2.5-flash` | Intake agent model |
| `TECHLENS_WRITER_MODEL` | No | `gemini-2.5-flash` | Writer agent model |
| `GOOGLE_GENAI_USE_VERTEXAI` | No | `0` | Set to `1` for Vertex AI auth |

## Deployment

Build from project root (not backend/):
```bash
docker build -f backend/Dockerfile -t techlens-backend .
```

Deploy to Cloud Run:
```bash
./deploy.sh --project YOUR_GCP_PROJECT_ID --region us-central1
```

## Contest

Built for the **Gemini Live Agent Challenge** by **Adair Labs**.

Demonstrates: Gemini model + Google GenAI SDK + ADK + GCP service (Cloud Run/Firestore) — real-time multimodal AI solving a real-world problem for auto repair technicians.

## License

MIT
