# TechLens — AI Diagnostic Copilot for Auto Repair Technicians

## What This Is

Hackathon entry for **Gemini Live Agent Challenge** (deadline: 2026-03-16 @ 5:00 PM PDT). Real-time multimodal AI assistant — voice + camera diagnosis with automated documentation. Solo build by Adair Labs.

## Tech Stack

- **Backend:** Python 3.12, FastAPI, Google ADK (`google-adk`), Google GenAI SDK (`google-genai`)
- **Frontend:** React 19, Vite, Tailwind CSS v4
- **AI:** Gemini Live API via ADK (model: `gemini-2.5-flash-native-audio-latest`)
- **Data:** In-memory JSON knowledge base (70KB, 3 Subaru vehicles, 8 TSBs, 175 NHTSA complaints)
- **Deploy:** Cloud Run + Firestore (session persistence)

## Architecture — Three-Agent Pipeline

```
SessionStart form → INTAKE AGENT (gemini-2.5-flash) → context package
                         ↓
                    LIVE AGENT (Gemini Live API, bidi-streaming) ← voice + camera
                         ↓
                    WRITER AGENT (gemini-2.5-flash) → Tech Notes, Customer Summary, Escalation Brief
```

### Three-State Session Model

- **IDLE** — WebSocket alive, no streaming. Zero tokens.
- **LISTENING** — Audio streaming to Gemini Live. 15-min cap.
- **LOOKING** — Audio + video (1 FPS JPEG). Auto-stops after 15s. Falls back to LISTENING.

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
│   ├── seed_data.py            # Firestore seed script
│   ├── Dockerfile
│   └── .env                    # GOOGLE_API_KEY (not committed)
├── frontend/
│   └── src/
│       ├── App.jsx             # Phase state machine (setup→active→review)
│       ├── components/         # SessionStart, LiveSession, AudioControls, CameraFeed, SessionOutputs
│       └── hooks/              # useWebSocket, useAudioStream, useCameraStream
├── test_knowledgebase/
│   └── techlens_knowledge_base.json  # Primary KB (3 vehicles, 14 issues, 8 TSBs)
├── research-docs/              # Competitive analysis, data sourcing notes
└── docs/superpowers/
    ├── specs/                  # Design spec
    └── plans/                  # Implementation plan
```

## Key Files to Read First

1. `docs/superpowers/plans/2026-03-13-techlens-mvp-implementation.md` — Full implementation plan with 14 tasks
2. `docs/superpowers/specs/2026-03-13-techlens-mvp-design.md` — Design spec with architecture details
3. `backend/main.py` — The WebSocket orchestrator (central integration point)
4. `frontend/src/components/LiveSession.jsx` — Frontend integration hub

## Running Locally

```bash
# Backend
cd backend && source .venv/bin/activate
cp .env.example .env  # Add your GOOGLE_API_KEY
uvicorn main:app --reload --port 8080

# Frontend
cd frontend && npm run dev
```

## Conventions

- **ADK patterns:** Use `LiveRequestQueue.send_realtime(blob)` for audio/video, `send_content(content)` for text
- **Audio:** 16kHz PCM-16 input, 24kHz PCM-16 output
- **Video:** JPEG at 1 FPS, 70% quality, rear camera (`facingMode: 'environment'`)
- **Env vars:** `TECHLENS_MODEL` overrides the live model, `GOOGLE_API_KEY` for AI Studio auth
- **Error handling:** All agents have fallback outputs when Gemini calls fail — demo must never crash

## Contest Requirements

Must use: Gemini model + Google GenAI SDK or ADK + at least 1 GCP service + hosted on Cloud Run. Demo video < 4 min. Architecture diagram required.

## What Matters for Judging

1. **Vision is the moat** — the "look at this" camera moment is THE differentiator
2. **Demo video is 30% of score** — working demo > pretty UI
3. **Richard's dealership experience** is the unfair advantage — lead with it in the pitch
