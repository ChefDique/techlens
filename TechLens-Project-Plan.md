# TechLens — Project Plan & Architecture

**Hackathon:** Gemini Live Agent Challenge
**Deadline:** March 16, 2026 @ 5:00 PM PDT
**Category:** Live Agent
**Builder:** Adair Labs (solo)

---

## 1. What We're Building

A real-time multimodal AI assistant for auto repair technicians. The tech speaks to TechLens hands-free while working on a vehicle. The agent:

- Narrows its knowledge base to the specific year/make/model
- References manufacturer service manuals and TSBs
- Uses voice + phone camera to assist with diagnosis in real time
- Generates 3 output documents from a single session:
  1. **Tech Notes** — structured repair notes for the technician's records
  2. **Customer Summary** — plain-English explanation for the service advisor to share
  3. **Escalation Brief** — detailed symptom/diagnostic data for manufacturer reps

---

## 2. Contest Requirements Checklist

### Mandatory (disqualified without these)

| # | Requirement | Our Solution | Status |
|---|------------|--------------|--------|
| 1 | Gemini model | `gemini-2.0-flash-live-preview-04-09` | ⬜ |
| 2 | Google GenAI SDK or ADK | ADK (Python) with bidi-streaming | ⬜ |
| 3 | At least 1 Google Cloud service | Cloud Run + Cloud Firestore + Vertex AI | ⬜ |
| 4 | Hosted on Google Cloud | FastAPI backend on Cloud Run | ⬜ |
| 5 | Live API or ADK (Live Agent category) | Gemini Live API via ADK | ⬜ |
| 6 | NEW project created during contest | Fresh repo, all new code | ⬜ |

### Submission Deliverables (all 5 required)

| # | Deliverable | Notes |
|---|------------|-------|
| 1 | Text description | Features, tech stack, data sources, learnings |
| 2 | Public GitHub repo | Clean README with spin-up instructions |
| 3 | GCP deployment proof | Screen recording of Cloud Run in GCP console |
| 4 | Architecture diagram | Visual: React → Cloud Run → Gemini Live API → Firestore |
| 5 | Demo video (<4 min) | Live demo at a vehicle + pitch the problem/value |

### Bonus Points (do all 3)

| # | Bonus | Effort |
|---|-------|--------|
| 1 | Blog/video about build process with #GeminiLiveAgentChallenge | 30 min on Day 3 |
| 2 | Automated cloud deployment (Dockerfile + deploy script in repo) | Built into Day 1 |
| 3 | Google Developer Group signup + link public profile | 5 min |

---

## 3. Tech Stack (All-Google Where It Counts)

```
┌─────────────────────────────────────────────────────┐
│                    FRONTEND                          │
│         React + Tailwind CSS (Web App)               │
│   - Mic input (MediaRecorder API → PCM 16kHz)       │
│   - Camera stream (getUserMedia → frames)            │
│   - Session controls (start/stop/vehicle select)     │
│   - Output display (3 document views)                │
│   - WebSocket connection to backend                  │
└──────────────────────┬──────────────────────────────┘
                       │ WebSocket (audio + video frames)
                       ▼
┌─────────────────────────────────────────────────────┐
│              BACKEND (Cloud Run)                     │
│         Python FastAPI + ADK Framework               │
│                                                      │
│   ADK Agent: "TechLens"                              │
│   ├── System instruction (tech assistant persona)    │
│   ├── Tools:                                         │
│   │   ├── lookup_vehicle_info(year, make, model)     │
│   │   ├── search_tsb(keywords, vehicle)              │
│   │   ├── get_diagnostic_flow(symptom, vehicle)      │
│   │   └── generate_session_outputs(session_data)     │
│   └── LiveRequestQueue (bidi-streaming)              │
│                                                      │
│   Gemini Live API Connection:                        │
│   - Audio in/out (voice conversation)                │
│   - Image frames (camera vision)                     │
│   - Tool calls (Firestore lookups)                   │
│   - Session transcription                            │
└──────┬──────────────────────────┬───────────────────┘
       │                          │
       ▼                          ▼
┌──────────────┐      ┌─────────────────────┐
│  Cloud       │      │  Gemini Live API     │
│  Firestore   │      │  (Vertex AI)         │
│              │      │                      │
│  Collections:│      │  Model:              │
│  - vehicles  │      │  gemini-2.0-flash    │
│  - tsbs      │      │  -live-preview       │
│  - sessions  │      │                      │
│  - manuals   │      │  Modalities:         │
│              │      │  - Audio (in/out)    │
│              │      │  - Image (in)        │
│              │      │  - Text (tool calls) │
└──────────────┘      └─────────────────────┘
```

---

## 4. Firestore Data Model

### Collection: `vehicles`
```json
{
  "id": "subaru_outback_2024",
  "year": 2024,
  "make": "Subaru",
  "model": "Outback",
  "engine": "2.5L DOHC",
  "transmission": "CVT",
  "common_issues": [
    "CVT hesitation at low speed",
    "Windshield cracking from stress points",
    "Battery drain from eyesight module"
  ]
}
```

### Collection: `tsbs`
```json
{
  "id": "tsb_15-235-18R",
  "number": "15-235-18R",
  "title": "CVT Chain Noise / Judder at Low Speed",
  "vehicle_years": [2020, 2021, 2022, 2023, 2024],
  "make": "Subaru",
  "models": ["Outback", "Legacy", "Forester"],
  "symptom": "Chain noise or judder during low speed acceleration",
  "fix": "Update TCM software and replace CVT fluid",
  "parts": ["SOA868V9350", "K0410Y0710"],
  "labor_hours": 1.5
}
```

### Collection: `sessions`
```json
{
  "id": "session_abc123",
  "vehicle_id": "subaru_outback_2024",
  "ro_number": "RO-44521",
  "customer_concern": "Noise from front end when turning",
  "transcript": "...(full session transcript)...",
  "findings": ["Torn CV boot, passenger side", "Grease on subframe"],
  "tsbs_referenced": ["tsb_15-235-18R"],
  "outputs": {
    "tech_notes": "...",
    "customer_summary": "...",
    "escalation_brief": "..."
  },
  "created_at": "2026-03-14T10:30:00Z"
}
```

---

## 5. ADK Agent Definition (Pseudocode)

```python
from google.adk import Agent
from google.adk.tools import FunctionTool

# Tool functions that query Firestore
def lookup_vehicle_info(year: int, make: str, model: str) -> dict:
    """Look up vehicle specs, common issues, and service history."""
    # Query Firestore vehicles collection
    ...

def search_tsb(keywords: str, year: int, make: str, model: str) -> list:
    """Search technical service bulletins for this vehicle."""
    # Query Firestore tsbs collection
    ...

def generate_session_outputs(transcript: str, findings: list, vehicle: dict) -> dict:
    """Generate tech notes, customer summary, and escalation brief."""
    # Uses Gemini to transform raw transcript into 3 formatted outputs
    ...

# Agent definition
techlens_agent = Agent(
    name="TechLens",
    model="gemini-2.0-flash-live-preview-04-09",
    instruction="""You are TechLens, an expert automotive diagnostic assistant.
    You are helping a service technician diagnose and repair a vehicle.

    Your behavior:
    - Speak clearly and concisely like a senior master tech
    - When the tech tells you the year/make/model, immediately look up
      the vehicle info and relevant TSBs
    - Guide diagnosis step by step, referencing service manual procedures
    - When you see something through the camera, describe what you observe
      and offer diagnostic recommendations
    - Track everything the tech says and does for session documentation
    - When the tech says "wrap up" or "done", generate the three outputs

    You are NOT a replacement for the tech's expertise. You are a hands-free
    co-pilot that handles the documentation and reference lookup so the tech
    can focus on the car.
    """,
    tools=[
        FunctionTool(lookup_vehicle_info),
        FunctionTool(search_tsb),
        FunctionTool(generate_session_outputs),
    ]
)
```

---

## 6. Three-Day Sprint Plan

### Day 1 (Today) — Foundation

**GCP Setup (1 hour)**
- [x] Create GCP project
- [ ] Enable APIs: Vertex AI, Cloud Run, Firestore, Cloud Build
- [ ] Request $100 credits
- [ ] Get Gemini API key from AI Studio (for local dev)
- [ ] Set up gcloud CLI locally

**Backend Scaffold (3-4 hours)**
- [ ] Init Python project with FastAPI
- [ ] Install ADK: `pip install google-adk`
- [ ] Install GenAI SDK: `pip install google-genai`
- [ ] Create basic ADK agent with system instruction
- [ ] Get bidi-streaming working (text first, then audio)
- [ ] Create Dockerfile
- [ ] Test locally

**Firestore Seed Data (1-2 hours)**
- [ ] Create Firestore database in GCP console
- [ ] Write seed script for 2-3 Subaru models you know well
- [ ] Add 5-10 real TSBs you remember
- [ ] Add common diagnostic flows

**Frontend Scaffold (1-2 hours)**
- [ ] Create React app (Vite + Tailwind)
- [ ] Build session start screen (year/make/model + RO number)
- [ ] WebSocket connection to backend
- [ ] Basic mic input capture

### Day 2 (Tomorrow) — Core Features

**Voice + Vision Integration (3-4 hours)**
- [ ] Wire up audio streaming (mic → backend → Gemini → speaker)
- [ ] Wire up camera frames (getUserMedia → backend → Gemini)
- [ ] Test real conversation flow with vehicle diagnosis
- [ ] Implement tool calls (vehicle lookup, TSB search)

**Output Generation (2-3 hours)**
- [ ] Build the 3-output generation logic
- [ ] Tech Notes format
- [ ] Customer Summary format
- [ ] Escalation Brief format
- [ ] Display outputs in frontend after session ends

**Deploy to Cloud Run (1-2 hours)**
- [ ] Build and push Docker image
- [ ] Deploy to Cloud Run
- [ ] Test deployed version
- [ ] Screen record GCP console for submission proof

### Day 3 (March 15) — Polish & Submit

**Demo Video (2-3 hours)**
- [ ] Script the 4-minute video flow
- [ ] Record at a real vehicle if possible (or use a detailed mockup)
- [ ] Show: problem statement → live demo → 3 outputs → value prop
- [ ] Edit and finalize

**Architecture Diagram (30 min)**
- [ ] Create clean visual diagram
- [ ] Add to repo README and submission

**Submission Package (1-2 hours)**
- [ ] Final text description (update the markdown from signup)
- [ ] Clean up GitHub repo + README with spin-up instructions
- [ ] Upload demo video
- [ ] Upload architecture diagram
- [ ] Upload GCP deployment proof recording
- [ ] Submit before 5:00 PM PDT March 16

**Bonus Points (1 hour)**
- [ ] Write quick blog post or record video about the build
- [ ] Sign up for Google Developer Group
- [ ] Verify Dockerfile serves as infrastructure-as-code

---

## 7. Key Files Structure

```
techlens/
├── backend/
│   ├── main.py                 # FastAPI app + WebSocket endpoint
│   ├── agent.py                # ADK agent definition + tools
│   ├── tools/
│   │   ├── vehicle_lookup.py   # Firestore vehicle queries
│   │   ├── tsb_search.py       # Firestore TSB queries
│   │   └── output_generator.py # 3-output generation logic
│   ├── seed_data.py            # Script to populate Firestore
│   ├── requirements.txt
│   └── Dockerfile
├── frontend/
│   ├── src/
│   │   ├── App.jsx
│   │   ├── components/
│   │   │   ├── SessionStart.jsx    # Vehicle/RO input form
│   │   │   ├── LiveSession.jsx     # Active diagnosis view
│   │   │   ├── AudioControls.jsx   # Mic/speaker controls
│   │   │   ├── CameraFeed.jsx      # Camera preview
│   │   │   └── SessionOutputs.jsx  # 3 output documents
│   │   └── hooks/
│   │       ├── useWebSocket.js     # WS connection to backend
│   │       ├── useAudioStream.js   # Mic capture → PCM
│   │       └── useCameraStream.js  # Camera → frames
│   ├── package.json
│   └── vite.config.js
├── deploy.sh                   # gcloud run deploy script (bonus)
├── architecture-diagram.png
└── README.md
```

---

## 8. Demo Vehicle Data to Seed

Focus on what you know cold. Seed these Subaru models:

1. **2024 Subaru Outback 2.5L** — CVT issues, eyesight calibration, windshield stress cracks
2. **2023 Subaru Forester** — Oil consumption, AC compressor, wheel bearing noise
3. **2022 Subaru Crosstrek** — Starter motor, CVT judder, rear brake squeal

For each: 3-5 common issues, 2-3 TSBs, basic diagnostic flows.

This is enough data to make the demo compelling. You can always say "we'd expand the knowledge base to all manufacturers" in the pitch.

---

## 9. Demo Video Script Outline (< 4 min)

**0:00-0:30 — The Problem**
"I worked at a Subaru dealership. Every day I watched techs struggle to document their work. Their notes were unreadable. Customers got confused. Manufacturer escalations got bounced back because there wasn't enough detail. I was the translator between all of them. TechLens automates that translation."

**0:30-1:00 — What TechLens Is**
Show the app. Explain the concept in 30 seconds.

**1:00-3:00 — Live Demo**
- Start a session: "2024 Outback, customer says noise from the front end when turning"
- Talk through a diagnosis naturally
- Point camera at vehicle components (if possible)
- Ask TechLens about TSBs
- Say "wrap it up"
- Show the 3 generated outputs

**3:00-3:30 — Architecture**
Flash the architecture diagram. Mention ADK, Gemini Live API, Cloud Run, Firestore.

**3:30-4:00 — What's Next**
DMS integration, more manufacturers, wearable glasses, industry-wide documentation standard.

---

## 10. Risk Mitigation

| Risk | Mitigation |
|------|-----------|
| Live API audio is janky | Fall back to text-based demo + explain voice is WIP |
| Camera/vision doesn't work well | Pre-capture images, send as frames. Demo still shows multimodal |
| Cloud Run deploy fails | Have local demo ready, show GCP console proof separately |
| Not enough time for polish | Prioritize: working demo > pretty UI > bonus points |
| Firestore data is thin | Small but real data > fake comprehensive data. Quality over quantity |

---

## Remember

- Judges may not test the app — they might judge on video + description alone
- The demo video is worth 30% of the score. Make it good.
- Your dealership experience is the unfair advantage. Lead with it.
- Ship ugly. Polish later. A working demo beats a pretty mockup.
