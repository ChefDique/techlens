# TechLens MVP Design Spec

**Date:** 2026-03-13
**Deadline:** 2026-03-16 @ 5:00 PM PDT
**Author:** Adair Labs (Richard + Claude)
**Status:** Draft

---

## 1. Product Vision (One Line)

TechLens is a hands-free AI copilot for auto repair technicians — voice + camera diagnosis with automated documentation, all without picking up a tablet.

## 2. MVP Scope

### Existing Code Base (Already Built)
- `backend/main.py` — 250-line FastAPI app with WebSocket endpoint, ADK runner, audio/video/JSON routing
- `backend/agent.py` — Single ADK agent with 3 tools (vehicle_lookup, tsb_search, output_generator)
- `backend/tools/vehicle_lookup.py` — Firestore-with-stub-fallback vehicle queries (3 Subaru models)
- `backend/tools/tsb_search.py` — Firestore-with-stub-fallback TSB search (7 TSBs)
- `backend/tools/output_generator.py` — Stub that generates template strings (NOT a Gemini call)
- Full frontend: React + Tailwind + WebSocket + audio capture + camera capture + ADK event parsing
- Knowledge base JSON: 70KB, 3 vehicles, 14 field issues, 8 TSBs, 175 NHTSA complaints

### In Scope — Refactor & Extend (Demo-Visible)
- Refactor single-agent → three-agent pipeline: Intake → Live → Writer
- Three-state session model: IDLE / LISTENING / LOOKING
- On-demand camera vision ("look at this" trigger) with auto-stop
- Unified knowledge base tool replacing separate vehicle_lookup + tsb_search
- Writer agent: separate Gemini call generates all 3 outputs (Tech Notes, Customer Summary, Escalation Brief)
- Frontend: intake loading state, camera auto-stop, end-session handoff to Writer outputs

### Out of Scope (Post-Hackathon)
- Dedicated async Research agent (collapsed into Live agent tool for MVP)
- DMS integration
- Multi-manufacturer support
- Session persistence/history across sessions
- Wake word detection (stretch goal — tap-to-talk is primary)
- AR glasses / wearable integration

---

## 3. Three-State Session Architecture

### States

| State | WebSocket | Audio | Video | Gemini Live | Token Cost | Duration Cap |
|-------|-----------|-------|-------|-------------|------------|--------------|
| IDLE | Connected (heartbeat) | OFF | OFF | Disconnected | Zero | Unlimited |
| LISTENING | Connected | Streaming | OFF | Connected | Moderate | 15 min |
| LOOKING | Connected | Streaming | Streaming (1 FPS) | Connected | High | ~15s bursts |

### State Transitions

```
                    tap mic / wake word
            IDLE ──────────────────────→ LISTENING
             ↑                              │  ↑
             │ 30s silence timeout          │  │
             └──────────────────────────────┘  │
                                               │  "look at this" / tap camera
                                               ↓
                                           LOOKING
                                               │
                                  auto-stop after 10-15s
                                  or agent says "got it"
                                               │
                                               ↓
                                           LISTENING
```

### Connection Architecture

```
Phone ←── WebSocket (always alive) ──→ FastAPI Backend ←── Live API (on demand) ──→ Gemini
```

The WebSocket between phone and backend is persistent (heartbeat ping/pong every 30s). The Gemini Live API connection opens/closes with state transitions. ADK's `SessionResumptionConfig` carries conversation context across reconnections so the tech experiences one continuous session.

### LOOKING State Details

- Camera activates on trigger phrase or tap
- Streams JPEG frames at 1 FPS via WebSocket
- Backend forwards frames as `types.Blob(mime_type="image/jpeg")` to `LiveRequestQueue.send_realtime()`
- Auto-stops after 10-15 seconds OR when agent acknowledges ("I can see the...")
- Falls back to LISTENING (not IDLE) — conversation continues
- Multiple LOOKING bursts allowed per session — each is short, totaling well under 2-min video cap

---

## 4. Agent Architecture

### Agent 1: INTAKE (Non-Live Gemini)

**When:** Runs once when tech submits the session start form.
**Model:** `gemini-2.5-flash` (standard, non-live)
**Input:** Year, make, model, RO number, customer concern
**Job:** Queries knowledge base, synthesizes a focused context package

**Process:**
1. Look up vehicle in `techlens_knowledge_base.json` / Firestore
2. Match customer concern keywords against known issues and TSBs
3. Generate a structured context package with only relevant data
4. Return JSON that becomes the Live agent's system instruction prefix

**Output Schema:**
```json
{
  "vehicle": {
    "id": "subaru_outback_2023",
    "year": 2023,
    "make": "Subaru",
    "model": "Outback",
    "engine": "FB25 2.5L DOHC Boxer",
    "transmission": "Lineartronic CVT",
    "safety_systems": ["EyeSight", "..."]
  },
  "relevant_tsbs": [
    {
      "number": "02-157-22R",
      "title": "CVT Judder / Hesitation at Low Speed",
      "symptom": "...",
      "fix": "...",
      "parts": ["..."]
    }
  ],
  "relevant_issues": [
    {
      "name": "Windshield stress cracking",
      "symptoms": ["..."],
      "diagnostic_steps": ["..."],
      "common_fix": "..."
    }
  ],
  "complaint_patterns": "83 NHTSA complaints. Top: windshield (15), eyesight (8)...",
  "customer_concern_analysis": "Noise when turning → likely CV joint, wheel bearing, or steering related",
  "suggested_diagnostic_flow": [
    "Reproduce the noise on a test drive or on the lift",
    "Isolate left vs right by turning lock-to-lock",
    "Inspect CV boots for tears, check for grease on subframe",
    "Check wheel bearing play with vehicle on lift"
  ]
}
```

**Why separate from Live agent:** The Live agent's context window is precious — it's handling real-time audio + video + conversation. Pre-filtering the knowledge base means the Live agent only gets what it needs, keeping it fast and coherent.

### Agent 2: LIVE (Gemini Live API via ADK)

**When:** Active during LISTENING and LOOKING states.
**Model:** `gemini-2.5-flash-native-audio-latest` (matches existing agent.py; env override via `TECHLENS_MODEL`)
**Input:** Intake context package injected into system instruction + real-time audio/video
**Job:** Real-time voice conversation, camera vision, tool calls

**System Instruction (template):**
```
You are TechLens, an expert automotive diagnostic copilot assisting a service
technician in real time. You speak like a senior master tech — clear, concise,
no fluff.

CURRENT SESSION CONTEXT:
{intake_context_json}

Your behavior:
- Reference the vehicle specs and known issues provided above
- When the tech describes symptoms, correlate with the TSBs and known issues
- When you see something through the camera, describe what you observe and
  offer diagnostic recommendations
- Guide diagnosis step by step, referencing the suggested diagnostic flow
- If the tech asks about something not in your current context, use the
  search_knowledge_base tool to find it
- Track everything for documentation — symptoms described, components inspected,
  findings, decisions made
- When the tech says "wrap it up" or "done", summarize findings verbally and
  signal session end

You are NOT replacing the tech's expertise. You are a hands-free co-pilot that
handles reference lookup and documentation so the tech can focus on the car.
```

**Tools (registered on ADK Agent):**
1. `search_knowledge_base(query, vehicle_id)` — searches TSBs, known issues, complaints beyond what Intake pre-loaded. This is the collapsed Research agent.
2. `log_finding(description, component, severity)` — explicitly logs a diagnostic finding for the Writer agent later. Called when the tech confirms something ("yep, CV boot is torn").

**ADK handles tool execution automatically** — no manual function_call/response cycle needed.

### Agent 3: WRITER (Non-Live Gemini)

**When:** Runs once after session ends.
**Model:** `gemini-2.5-flash` (standard, non-live)
**Input:** Full session transcript + Intake context package + logged findings
**Job:** Generate polished Tech Notes document

**Tech Notes Output Format:**
```
TECH NOTES — RO# {ro_number}
{date}

VEHICLE: {year} {make} {model} — {engine} / {transmission}
TECHNICIAN: {tech_name}

CUSTOMER CONCERN:
{original_concern}

DIAGNOSTIC PROCEDURE:
1. {step_and_finding}
2. {step_and_finding}
...

FINDINGS:
- {finding_1} [{severity}]
- {finding_2} [{severity}]

TSBs REFERENCED:
- {tsb_number}: {title} — {applicable/not applicable}

RECOMMENDED REPAIRS:
1. {repair} — Parts: {parts} — Labor: {hours}h
2. {repair} — Parts: {parts} — Labor: {hours}h

NOTES:
{additional_context_from_tech}
```

**Why separate from Live agent:** The Live agent's transcript is messy — it has false starts, "uhhs", tangents, background noise transcription. A fresh Gemini call with clean instructions produces dramatically better documentation than asking the Live agent to generate it mid-conversation.

---

## 5. Backend Architecture

### File Structure

```
backend/
├── main.py                    # [EXISTS — REFACTOR] Add state machine, intake/writer orchestration
├── agent.py                   # [EXISTS — REPLACE] Currently single agent → becomes live_agent only
├── agents/
│   ├── __init__.py            # [NEW]
│   ├── intake_agent.py        # [NEW] Intake agent definition + KB query logic
│   ├── live_agent.py          # [NEW] Live ADK agent (migrated from agent.py + new system prompt)
│   └── writer_agent.py        # [NEW] Writer agent for 3-document generation
├── tools/
│   ├── __init__.py            # [EXISTS]
│   ├── vehicle_lookup.py      # [EXISTS — KEEP] Used by intake agent
│   ├── tsb_search.py          # [EXISTS — KEEP] Used by intake agent
│   ├── output_generator.py    # [EXISTS — REMOVE] Replaced by writer_agent.py
│   └── knowledge_base.py      # [NEW] Unified KB search tool for Live agent
├── models/
│   ├── __init__.py            # [NEW]
│   └── session_state.py       # [NEW] Session state enum + data models
├── seed_data.py               # [EXISTS]
├── requirements.txt           # [EXISTS]
├── Dockerfile                 # [EXISTS]
├── .env                       # [EXISTS]
└── .env.example               # [EXISTS]
```

### main.py — WebSocket Endpoint

```python
# Pseudocode — actual implementation will follow ADK patterns

app = FastAPI()

@app.websocket("/ws/{user_id}/{session_id}")
async def session_endpoint(websocket, user_id, session_id):
    await websocket.accept()
    session_state = SessionState.IDLE
    live_queue = None
    live_task = None
    intake_context = None

    async def handle_message(message):
        nonlocal session_state, live_queue, intake_context

        if message.type == "start_session":
            # Run Intake agent
            intake_context = await run_intake_agent(message.vehicle, message.concern)
            await websocket.send_json({"type": "intake_complete", "context": intake_context})

        elif message.type == "activate_listening":
            # Transition IDLE → LISTENING
            live_queue = LiveRequestQueue()
            live_task = start_live_agent(live_queue, intake_context, user_id, session_id)
            session_state = SessionState.LISTENING

        elif message.type == "activate_looking":
            # Transition LISTENING → LOOKING (Live session stays open)
            session_state = SessionState.LOOKING

        elif message.type == "deactivate_looking":
            # Transition LOOKING → LISTENING
            session_state = SessionState.LISTENING

        elif message.type == "end_session":
            # Close Live agent, run Writer agent
            live_queue.close()
            tech_notes = await run_writer_agent(transcript, intake_context, findings)
            await websocket.send_json({"type": "session_outputs", "tech_notes": tech_notes})

    # Main loop: receive from WebSocket, route to appropriate handler
    # Binary data → audio blob → live_queue.send_realtime()
    # JSON with video_frame → image blob → live_queue.send_realtime()
    # JSON with other types → handle_message()
    #
    # Concurrently: live agent events → websocket.send_json()
```

### Key Implementation Details

**Audio flow:**
1. Frontend captures mic at 16kHz PCM-16 via ScriptProcessor
2. Sends as binary ArrayBuffer over WebSocket every 250ms
3. Backend wraps in `types.Blob(mime_type="audio/pcm;rate=16000", data=bytes)`
4. Feeds to `live_queue.send_realtime(blob)`
5. Gemini responds with audio events containing inline PCM-16 at 24kHz
6. Backend forwards event JSON to frontend via WebSocket
7. Frontend decodes and plays via Web Audio API at 24kHz

**Video flow:**
1. Frontend captures rear camera frame as JPEG (70% quality) at 1 FPS
2. Sends as JSON `{ type: "video_frame", data: "<base64>" }` over WebSocket
3. Backend decodes base64, wraps in `types.Blob(mime_type="image/jpeg", data=bytes)`
4. Feeds to `live_queue.send_realtime(blob)`
5. Agent processes frame and responds verbally about what it sees

**Transcript accumulation:**
- Backend accumulates `input_transcription` and `output_transcription` events from ADK
- Stored in a session-level list: `[{role: "tech", text: "..."}, {role: "agent", text: "..."}]`
- Passed to Writer agent at session end

---

## 6. Frontend Changes Required

### Minimal — frontend is 90% built

**SessionStart.jsx** — Minor change: default year from 2024 → 2023 to match knowledge base vehicles.

**LiveSession.jsx** — Changes needed:
- Add intake phase: after form submit, show "Preparing session..." while Intake agent runs
- Receive `intake_complete` event before enabling mic
- Add camera trigger button (already exists but needs state tie-in)
- Handle `session_outputs` event to transition to review phase with Tech Notes data

**AudioControls.jsx** — No changes.

**CameraFeed.jsx** — Minor changes:
- Auto-stop timer (10-15 seconds)
- Visual countdown indicator

**SessionOutputs.jsx** — Minor changes:
- Display Tech Notes from Writer agent output
- Display all 3 outputs (Tech Notes, Customer Summary, Escalation Brief) — tabs already exist

**hooks/useWebSocket.js** — No changes.
**hooks/useAudioStream.js** — No changes.
**hooks/useCameraStream.js** — No changes.

### New: Wake Word Detection (Stretch Goal)

If time permits, add `hooks/useWakeWord.js`:
- Uses `webkitSpeechRecognition` (Web Speech API) for on-device phrase detection
- Listens for: "hey techlens", "techlens", "look at this", "check this out"
- Fires callback to transition states
- Zero token cost — runs entirely in browser
- Graceful degradation: if Web Speech API unavailable, tap-to-talk buttons are primary

---

## 7. Knowledge Base Integration

### Data Source

Primary: `/test_knowledgebase/techlens_knowledge_base.json` (70KB)
- 3 vehicles with full specs
- 14 known field issues with diagnostic procedures
- 8 TSBs/recalls with real numbers
- 175 categorized NHTSA complaints

Secondary: Raw complaint files (~180KB total)
- `complaints_outback_2023.json`
- `complaints_forester_2023.json`
- `complaints_crosstrek_2023.json`

### Loading Strategy (MVP)

For MVP, load the knowledge base JSON into memory at server startup. No Firestore required for the demo. The Intake agent queries this in-memory data. The existing `vehicle_lookup.py` and `tsb_search.py` tools already have stub fallbacks that work without Firestore.

**Post-hackathon:** Migrate to Firestore with the existing `seed_data.py` script. For Cloud Run deployment, the JSON file ships in the Docker image.

### Firestore (Contest Requirement)

The contest requires at least 1 Google Cloud service. Options:
1. **Firestore for session storage** — save session transcripts and outputs after each session. Lightweight, satisfies the requirement, and is genuinely useful.
2. **Firestore for KB** — seed the knowledge base into Firestore collections. More impressive but more work.

**Recommendation:** Option 1. Load KB from JSON in-memory, use Firestore only for session persistence. Mention in the pitch that "production deployment stores the knowledge base in Firestore for dynamic updates."

---

## 8. Deployment Architecture

```
┌─────────────────┐     ┌──────────────────────┐     ┌─────────────┐
│   Phone/Browser  │────→│   Cloud Run           │────→│ Gemini Live │
│   (React SPA)    │←────│   (FastAPI + ADK)     │←────│ API         │
│                  │ WS  │                       │     │             │
│   - Audio capture│     │   - WebSocket broker  │     │ - Audio I/O │
│   - Camera       │     │   - Intake agent      │     │ - Vision    │
│   - Wake word    │     │   - Live agent        │     │ - Tools     │
│   - Audio play   │     │   - Writer agent      │     │             │
│                  │     │   - KB in memory       │     └─────────────┘
└─────────────────┘     │                       │
                        │   ┌──────────────┐    │
                        │   │  Firestore    │    │
                        │   │  (sessions)   │    │
                        │   └──────────────┘    │
                        └──────────────────────┘
```

### Cloud Run Config
- Min instances: 1 (avoid cold start during demo)
- Max instances: 1 (hackathon, single user)
- Memory: 512MB
- CPU: 1
- Timeout: 900s (15 min, matches max audio session)
- WebSocket support: enabled (Cloud Run supports it natively)

### Frontend Deployment
- Build React SPA with Vite
- Serve static files from Cloud Run (same container) or deploy to Firebase Hosting
- **Recommendation:** Same container, simpler. FastAPI serves `/` as static files, `/ws/` as WebSocket.

---

## 9. Demo Script Alignment

The design maps directly to the competitive analysis "Dirty Hands Demo":

1. **Tech starts session** → fills in "2023 Outback, RO-44521, customer says noise when turning" → Intake agent runs (2-3 seconds) → "I've loaded the Outback profile. 6 known issues, 3 relevant TSBs. Ready when you are."

2. **Tech taps mic** → LISTENING state → "Alright, customer's saying they hear a clicking noise from the front end when they make sharp turns at low speed. What are we thinking?"
   → Agent: "On the 2023 Outback with the FB25, clicking on turns is usually a CV joint. I see a complaint pattern for this — 83 NHTSA complaints, several mention front-end noise. Let's start with a visual inspection of the CV boots."

3. **Tech says "look at this"** → LOOKING state → camera on → points at torn CV boot
   → Agent: "I can see a tear in the CV boot, passenger side. There's grease spray on the subframe which confirms it's been leaking for a while. This is consistent with the clicking symptom. I'm logging this as a finding."
   → Camera auto-stops after 10 seconds → back to LISTENING

4. **Tech says "wrap it up"** → Writer agent runs → Tech Notes appear on screen

5. **Show Tech Notes** → clean, professional, with real TSB numbers and findings

**Total demo time: ~3 minutes. Leaves 1 minute for architecture and "what's next."**

---

## 10. Build Strategy — Parallel Subagents

Three workstreams. WS-1 and WS-2 can run in parallel since the WebSocket message contract is already defined by the existing frontend/backend code.

| Workstream | Files | What Changes |
|-----------|-------|-------------|
| **WS-1: Agent Pipeline** | `agents/intake_agent.py`, `agents/live_agent.py`, `agents/writer_agent.py`, `tools/knowledge_base.py` | New files. Migrate logic from `agent.py`, add intake/writer Gemini calls, unified KB search |
| **WS-2: WebSocket Refactor** | `main.py`, `models/session_state.py` | Refactor existing 250-line main.py: add state machine (IDLE/LISTENING/LOOKING), intake orchestration, writer orchestration, transcript accumulation |
| **WS-3: Frontend Polish** | `LiveSession.jsx`, `CameraFeed.jsx`, `SessionOutputs.jsx`, `SessionStart.jsx` | Intake loading state, camera auto-stop, end-session handoff, year default fix |

WS-2 depends on WS-1's agent interfaces being defined (import paths, function signatures). Define those interfaces first, then both workstreams proceed in parallel. WS-3 can start immediately since the WebSocket contract is stable.

---

## 11. Risk Mitigation

| Risk | Mitigation |
|------|-----------|
| Gemini Live API audio quality in noisy shop | Demo in quiet environment. Mention "production version includes noise cancellation" |
| 2-min video session limit | LOOKING state auto-stops at 10-15s. Multiple bursts stay well under cap |
| Live API latency / connection drops | Session resumption carries context. Frontend shows reconnecting state |
| Knowledge base feels thin | Real NHTSA data + real TSB numbers + Richard's field expertise make it authentic |
| Cloud Run WebSocket timeout | Set timeout to 900s, add heartbeat keepalive |
| Intake agent slow (cold Gemini call) | Show loading state. In practice, non-live Gemini calls return in 2-3s |
| Wake word detection unreliable | Tap-to-talk is the primary UX. Wake word is stretch goal / demo enhancement |

---

## 12. Success Criteria

The demo video must show:
1. A real vehicle session start with authentic vehicle data
2. Natural voice conversation where the agent references real TSBs by number
3. At least one "look at this" camera moment where the agent identifies a component
4. Generated Tech Notes that look professional and accurate
5. The architecture diagram showing the multi-agent pipeline

If all 5 happen in under 4 minutes, we win.
