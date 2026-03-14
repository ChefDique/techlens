# TechLens — AI Diagnostic Copilot for Auto Repair Technicians

## What This Is

Hackathon entry for **Gemini Live Agent Challenge** (deadline: 2026-03-16 @ 5:00 PM PDT). Real-time multimodal AI assistant — voice + camera diagnosis with automated documentation. Solo build by Adair Labs.

## Tech Stack

- **Backend:** Python 3.13, FastAPI, Google ADK (`google-adk`), Google GenAI SDK (`google-genai`)
- **Frontend:** React 19, Vite, Tailwind CSS v4
- **AI:** Gemini Live API via ADK (model: `gemini-2.5-flash-native-audio-latest`)
- **Data:** In-memory JSON knowledge base — schema v1.0 (3 Subaru vehicles, 14 TSBs, 3 recalls, 175 NHTSA complaints)
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
│   │   ├── writer_agent.py     # Post-session document generation
│   │   └── synthesizer_agent.py # Layer 2: live session synthesis (WIP)
│   ├── tools/
│   │   └── knowledge_base.py   # Unified KB search — get_vehicle_profile, get_matching_tsbs, get_matching_recalls, search_knowledge_base, normalize_category
│   ├── models/
│   │   └── session_state.py    # SessionPhase, IntakeContext, SessionTranscript, SessionSynthesis, SessionOutputs, VehicleContext, RepairOrder, Session
│   ├── seed_data.py            # Firestore seed script (for Cloud Run deploy)
│   ├── Dockerfile
│   └── .env                    # GOOGLE_API_KEY (not committed)
├── frontend/
│   └── src/
│       ├── App.jsx             # Phase state machine (setup→active→review)
│       ├── components/         # SessionStart, LiveSession, ActiveContextPanel, AudioControls, CameraFeed, SessionOutputs
│       └── hooks/              # useWebSocket, useAudioStream, useCameraStream
├── test_knowledgebase/
│   └── techlens_knowledge_base.json  # Primary KB — schema v1.0 (3 vehicles, 14 TSBs, 3 recalls)
├── scripts/
│   └── migrate_kb_v1.py        # KB schema migration script (rerunnable, kept for reference)
├── ARCHITECTURE.md             # Deep technical doc + IP/moat analysis
└── README.md                   # Project overview with architecture diagrams
```

## Key Files to Read First

1. `ARCHITECTURE.md` — Full system architecture, design patterns, IP strategy
2. `backend/main.py` — The WebSocket orchestrator (central integration point)
3. `backend/agents/live_agent.py` — The Live API agent with dynamic context injection
4. `frontend/src/components/LiveSession.jsx` — Frontend integration hub
5. `backend/models/session_state.py` — All session/synthesis data models

## Running Locally

```bash
# Backend
cd backend && source .venv/bin/activate
source .env && export GOOGLE_API_KEY
uvicorn main:app --reload --port 8080

# Frontend (separate terminal)
cd frontend && npm run dev
```

Open `http://localhost:5173` — Vite proxies `/ws` to backend:8080.

## Schema v1.0 — The Contract

All KB documents follow a locked schema. Key conventions:
- Every document has `schema_version: "1.0"`, `type`, `ingested_at`
- `categories` use a **fixed 22-value taxonomy** (e.g. `POWER TRAIN`, `ENGINE`, `ELECTRICAL SYSTEM`) — see `TechLens-Orchestrator-Addendum.md` for full list
- `affected_vehicles` are always `{year_start, year_end, make, models}` objects — no strings, no year arrays
- `parts` are always `{part_number, description, quantity}` objects
- TSBs use `fix_summary` (not `fix`), have `diagnostic_steps[]`, `figures[]`, `related_dtcs[]`, `keywords[]`
- Recalls are top-level in KB JSON (not nested in vehicles)
- `trim_specific: true` TSBs require trim confirmation before giving instructions
- Dirty category data: use `normalize_category()` in `knowledge_base.py`

## Conventions

- **ADK patterns:** Use `LiveRequestQueue.send_realtime(blob)` for audio/video, `send_content(content)` for text
- **Audio:** 16kHz PCM-16 input, 24kHz PCM-16 output
- **Video:** JPEG at 1 FPS, 70% quality, rear camera (`facingMode: 'environment'`)
- **Env vars:** `TECHLENS_MODEL` overrides the live model, `GOOGLE_API_KEY` for AI Studio auth
- **Error handling:** All agents have fallback outputs when Gemini calls fail — demo must never crash
- **Gemini response parsing:** Always strip markdown fences from JSON responses (Gemini adds them non-deterministically)

## Conversation Agent Rules (Non-Negotiable)

1. **Confirm trim** before giving trim-specific instructions (`trim_specific: true`)
2. **Never improvise procedures** — if a referenced procedure isn't loaded, say so and offer to look it up
3. **Cite every instruction** — "Per TSB 02-157-22R, step 4..." — no uncited technical guidance
4. **Handle diagnostic branching** — present decision points, ask tech for results before proceeding
5. **Cross-reference awareness** — note when a document references another, offer to surface it

## Contest Requirements

Must use: Gemini model + Google GenAI SDK or ADK + at least 1 GCP service + hosted on Cloud Run. Demo video < 4 min. Architecture diagram required.

## What Matters for Judging

1. **~60% video presentation, ~40% code** — past winner analysis
2. **"Happy customer approach"** — show the problem being solved, the user delighted
3. **Vision is the moat** — the "look at this" camera moment is THE differentiator
4. **Richard's dealership experience** is the unfair advantage — lead with it in the pitch
