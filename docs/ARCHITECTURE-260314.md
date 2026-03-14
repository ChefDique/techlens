# TechLens — Sprint Plan for Coding Agent Orchestrator

## Context for the Orchestrator

You are building TechLens, a real-time multimodal AI assistant for auto repair technicians. This is a hackathon entry for the Gemini Live Agent Challenge. Deadline: March 16, 2026 @ 5:00 PM PDT.

The product uses a multi-agent architecture where a conversation agent handles real-time voice and vision with the technician, while background agents handle synthesis, research, and document processing. The conversation agent must remain fast and lean. All heavy processing happens off the conversation thread.

Tech stack: Python, FastAPI, Google ADK, Gemini Live API, Cloud Firestore, Cloud Run, React frontend, Docker.

The repo already has a working prototype with basic voice conversation via Gemini Live API. This sprint extends it into the full multi-agent system.

---

## What Must Be Built and Why

### 1. CONVERSATION AGENT (voice + vision thread)

**What:** The primary agent the technician talks to. Runs on Gemini Live API via ADK bidi-streaming. Handles real-time voice input/output and vision input when triggered.

**Why it must be its own agent:** This agent's context window must stay small and its response latency must stay under 2 seconds for natural conversation. If we load it with document search, synthesis tracking, or PDF processing, latency will spike and the demo will feel broken. The conversation agent talks from pre-loaded context and short structured data only. It never touches a PDF. It never does heavy processing.

**What it knows at session start:**
- Vehicle profile (specs, known issues, common DTCs) — injected into system prompt
- Top TSB summaries for this vehicle — injected into system prompt  
- Repair order details (customer concern, VIN, mileage) — injected into system prompt
- This gives it enough to handle ~80% of questions with zero tool calls

**Tools it has access to (fast, small returns only):**
- `search_tsb(keywords, vehicle)` → returns short JSON summary from Firestore, NOT a PDF
- `search_complaints(vehicle, component)` → returns top 3 matching complaint summaries
- `add_note(text)` → writes to session state, triggers synthesizer
- `flag_for_research(query)` → sends a request to the research agent asynchronously
- `request_visual(tsb_number, figure_number)` → tells frontend to display a specific diagram

**Trigger words it responds to:**
- "Yo Gemmy" / "Hey Gemmy" → confirms presence
- "Look at this" / "What do you see" → processes current video frame, gives quick 2-3 sentence response
- "Note that" / "Remember this" → calls add_note, confirms "Noted"
- "Is there a TSB" / "Any bulletins" → calls search_tsb
- "Wrap it up" / "Done" / "End session" → signals session end to all agents
- "Show me the diagram" / "Pull up the figure" → calls request_visual
- "Gemmy stop" / "Hold on" → stops speaking (native Live API barge-in)
- "What did the customer say" → reads back repair order concern from session state
- "Go back to [topic]" → references synthesized notes to pick up previous thread

**Build priority: HIGHEST — this must work flawlessly for the demo.**

---

### 2. SYNTHESIZER AGENT (background processing thread)

**What:** A separate agent (or process using Gemini API, not Live API) that runs in the background during the session. It watches the conversation transcript and periodically synthesizes it into structured context that all other agents can reference.

**Why it must exist:** 
1. The conversation agent's context window can't grow unbounded. As the session gets longer, response latency increases. The synthesizer compresses the conversation into a structured JSON context object that the conversation agent can reference without holding the full transcript.
2. The three output documents at session end need clean, structured source material — not a raw transcript dump. The synthesizer builds that material incrementally so the final generation is fast.
3. This is the core technology differentiator. Anyone can build a voice chatbot. The synthesis layer is what makes TechLens a professional tool, not a toy. When judges ask "how does this work," the synthesizer is the answer.

**What it produces:**
- A structured JSON context object (the "session.md" equivalent) that contains:
  - Current vehicle context
  - Findings so far (structured bullets)
  - TSBs referenced with relevance scores
  - Diagnostic steps taken
  - Tools/parts identified as needed
  - Blocking issues flagged
  - Open items remaining
- A bullet-point summary displayed in the Active Context Panel (what the user sees)
- Relevance-scored document references for the Related Documents panel

**When it runs (trigger conditions):**
- Every ~500 tokens of new transcript content (interval trigger)
- When the conversation agent calls `add_note()` (explicit trigger)
- When the conversation agent calls a tool and gets a result (tool result trigger)
- When the conversation agent identifies a key finding like a part number, measurement, DTC, or diagnosis conclusion (key finding trigger — detected by the synthesizer watching the transcript)

**Relevance scoring (determines what shows in the Active Context Panel):**
- Level 3 — CRITICAL: User explicitly flagged ("note that"), blocking issues (missing tool, safety concern, recall match), or confirmed diagnostic findings. Always shown in panel. Always included in all three outputs.
- Level 2 — RELEVANT: Directly matches current vehicle + current symptom + current diagnostic step. Shown in panel. Included in outputs if relevant to that output's audience.
- Level 1 — AMBIENT: Mentioned in passing, tangentially related, or conversational noise. NOT shown in panel by default. Stored in JSON for retrieval if needed later. The "leak diagnosis" joke is Level 1.

**Irrelevance detection:**
- If a topic is tagged Level 1 and not referenced again within the next 2 synthesis cycles, it stays in JSON but is marked as dormant
- If the user pivots to a different complaint line on the repair order, the synthesizer compresses the previous complaint to a summary block and makes the new complaint the active focus
- The JSON always retains everything — the panel is a curated view of what matters NOW

**Build priority: HIGH — this is the tech that wins. Even a simplified version that runs at intervals and produces structured bullets will impress. The relevance scoring can be prompt-engineered, not hard-coded logic.**

---

### 3. RESEARCH AGENT (async document retrieval)

**What:** An agent (or function) that retrieves and surfaces relevant documents, TSBs, diagrams, and reference material. It populates the Related Documents section of the Active Context Panel.

**Why it must be separate from the conversation agent:**
1. Document retrieval and processing is slow. If the conversation agent does it, the user hears dead air.
2. The research agent can work asynchronously — the conversation continues while documents surface in the background.
3. Documents contain visual diagrams that need to be served to the frontend, not read aloud by the agent. The research agent handles the visual content pipeline.

**What it does:**
- Receives requests from the conversation agent (`flag_for_research`) or from the synthesizer (when a new finding matches a known document)
- Queries Firestore for matching TSBs, service procedures, and NHTSA complaint data
- Returns structured references with:
  - Document title and number
  - Relevance score
  - Key page numbers / figure numbers for diagrams
  - A short text summary (for the conversation agent to speak from if asked)
  - A link/path to the full document (for the frontend to display)
- Pushes results to the frontend via WebSocket → they appear in the Related Documents panel

**How it handles diagrams:**
- TSBs and service manuals contain diagrams referenced by figure number
- When the research agent surfaces a TSB, it includes metadata about which figures are relevant to the current discussion
- The frontend can display these figures in the Related Documents popover
- The conversation agent can say "check figure 3 in the TSB I just pulled up" and the frontend already has it ready
- For the demo: we pre-process our demo TSBs to extract figure references. We don't need a general-purpose PDF diagram extractor — just metadata for 3-4 documents.

**Build priority: MEDIUM-HIGH — a simplified version that pushes TSB cards to the frontend when the conversation agent mentions a TSB number is sufficient for demo. Async background surfacing is the stretch goal.**

---

### 4. FRONTEND (React app)

**What:** The TechLens web application UI that displays during the demo as a slide-over panel alongside the cinematic video.

**Why it must look and feel like a real product:**
1. The UI is visible in the demo video from Scene 5 onward. It needs to look professional.
2. The judges may test the repo. The frontend must work when they run it.
3. The UI tells the story of what's happening technically. The Active Context Panel, the Related Documents, the three outputs — these prove the multi-agent system is real.

**Layout:**

TOP: Repair Order Bar
- RO number, year/make/model/trim, VIN, customer concern
- History tab (visible but inactive for demo)

LEFT COLUMN:
- Camera/mic input module (upper left)
  - Live video feed (or simulated pre-recorded feed)
  - Component identification overlay when vision active
  - Mic level indicator with active/inactive state
  - Speaker output level indicator
- Live Transcript (lower left)
  - Last 5-8 lines of conversation
  - Speaker labels: RICHARD / GEMMY / [OTHER]
  - New lines push up, scrollable, pinned to latest by default
  - Formatted differently per speaker (color or indentation)

RIGHT COLUMN: Active Context Panel
- Synthesized Notes (upper right)
  - Bullet points from synthesizer agent
  - Builds incrementally during session
  - Level 3 items highlighted/flagged
  - Level 2 items shown normally
  - Level 1 items hidden (available via "show all" toggle if needed)
- Related Documents (lower right)
  - Cards that slide in when research agent surfaces documents
  - Each card: document type icon, title, TSB number, brief description
  - Clickable → opens a popover with document content / figures
  - For demo: 3-4 pre-loaded documents that surface at the right moments

BOTTOM BAR:
- Session timer
- "End Session" button
- "Note That" button (manual trigger fallback)

SESSION END VIEW:
- Repair Order Bar stays
- Left + right columns replaced by three equal columns:
  - TECH NOTES (structured, clinical, part numbers, next steps)
  - CUSTOMER SUMMARY (plain English, no jargon, empathetic tone)
  - ESCALATION BRIEF (detailed, measurements, DTCs, all diagnostic steps, complete history)
- Each column has: [Copy] [Print/Email/Send] buttons

**Build priority: HIGH — this is what appears in the demo video. Use Tailwind, keep it clean, dark theme to match the 1950s aesthetic. Don't over-design. Functional and readable on camera is the bar.**

---

### 5. BACKEND INFRASTRUCTURE

**What:** FastAPI server that orchestrates all agents and serves the frontend.

**Endpoints:**
- `WebSocket /ws/session` — main connection for voice/vision bidi-streaming with conversation agent
- `WebSocket /ws/context` — pushes synthesizer updates and research results to frontend in real time
- `POST /api/session/start` — creates session, pre-loads vehicle context, initializes all agents
- `POST /api/session/end` — triggers output generation, stores session to Firestore
- `GET /api/vehicle/{year}/{make}/{model}` — returns vehicle profile for session start screen
- `GET /api/documents/{doc_id}` — returns document content for Related Documents popover

**Agent orchestration pattern:**
```
Frontend (React)
    │
    ├── WebSocket /ws/session ──→ Conversation Agent (ADK + Live API)
    │                                    │
    │                                    ├── tool call: add_note() ──→ Session State
    │                                    │                                │
    │                                    │                    Synthesizer Agent watches
    │                                    │                    transcript + session state
    │                                    │                                │
    │                                    ├── tool call: search_tsb() ──→ Firestore
    │                                    │                                │
    │                                    ├── tool call: flag_for_research() ──→ Research Agent
    │                                    │                                         │
    │                                    └── tool call: request_visual() ──→ Frontend
    │                                                                        (via /ws/context)
    │
    └── WebSocket /ws/context ←── Synthesizer Agent pushes updates
                               ←── Research Agent pushes document cards
```

**Build priority: HIGH — this is the backbone. The WebSocket connections must be solid. The agent orchestration must not block the conversation thread.**

---

### 6. DEPLOYMENT

**What:** Dockerized deployment to Google Cloud Run.

**Why:** Mandatory hackathon requirement. Must provide proof of GCP deployment.

**What's needed:**
- Dockerfile that builds the full app (backend + frontend)
- `deploy.sh` script for `gcloud run deploy` (bonus points for infrastructure-as-code)
- Environment variable config for Gemini API key and Firestore project
- README with exact spin-up instructions that judges can follow

**Build priority: MEDIUM — do this after the app works locally. Cloud Run deployment is straightforward if the Docker setup is clean.**

---

### 7. KNOWLEDGE BASE SEED DATA

**What:** Pre-processed vehicle data, TSBs, complaints, and diagnostic procedures ready to load into Firestore.

**Status: MOSTLY DONE.** We have:
- 3 vehicles with full specs, known issues, diagnostic procedures (JSON ready)
- 8 TSBs with structured summaries
- 175+ real NHTSA complaints categorized by component
- Common DTCs per vehicle

**What still needs to happen:**
- Seed script that writes all of this to Firestore collections
- Extract 3-4 TSB PDFs (or create representative ones) for the Related Documents demo
- Note which figures/diagrams in those TSBs are relevant to our demo scenarios
- Pre-process the vehicle documents into the pre-load format (small JSON blocks for system prompt injection)

**Build priority: MEDIUM — data exists, just needs to be loaded. Seed script is straightforward.**

---

## Sprint Execution Order

This is the order in which things should be built, based on dependencies and demo criticality.

### PHASE 1: Core conversation loop (must work first)
1. **Conversation Agent** — ADK agent with system prompt, connected to Live API, voice working
2. **Pre-loading pipeline** — session start pulls vehicle context from Firestore, injects into agent
3. **Basic tool calls** — search_tsb and add_note working, returning structured data
4. **Frontend skeleton** — repair order bar, transcript display, mic/camera modules

**Why this order:** Nothing else matters if the voice conversation doesn't work smoothly. This is the foundation everything else depends on. Test with a real conversation about a 2023 Outback CVT issue. If the agent responds fast and accurately from pre-loaded context, Phase 1 is done.

### PHASE 2: Multi-agent coordination
5. **Synthesizer Agent** — background process watching transcript, producing structured JSON and bullet summaries at intervals
6. **Active Context Panel** — frontend displays synthesizer output in real time via WebSocket
7. **Research Agent** — surfaces TSB cards and document references when triggered by conversation or synthesizer
8. **Related Documents panel** — frontend displays research results, clickable with popover

**Why this order:** The synthesizer is the core tech differentiator. Get it running before polishing the frontend. The research agent extends the synthesizer's output into document references. The frontend panels make both visible.

### PHASE 3: Session output and polish
9. **Three-output generation** — session end triggers Gemini call that reads synthesized JSON + transcript and produces tech notes, customer summary, and escalation brief
10. **Three-column output UI** — frontend displays the three documents with copy/print/send actions
11. **Vision mode** — "look at this" triggers video frame analysis from conversation agent
12. **Pre-recorded video pipeline** — ability to pipe pre-recorded video as webcam input for demo filming

**Why this order:** Outputs depend on the synthesizer working. Vision mode is important but the demo can survive without it if needed — the voice + synthesis + outputs flow is more critical.

### PHASE 4: Deployment and submission
13. **Dockerfile + deploy.sh** — containerize and deploy to Cloud Run
14. **GCP deployment proof** — screen record the Cloud Run console
15. **README** — spin-up instructions for judges
16. **Architecture diagram** — visual of the multi-agent system
17. **Demo video filming** — requires all of the above working
18. **Devpost submission** — text description, video, diagram, repo link, deployment proof

---

## Parallel Work Streams

These can be worked on simultaneously by different agents or in different sessions:

**Stream A: Backend agents** — conversation agent, synthesizer, research agent, FastAPI orchestration
**Stream B: Frontend** — React UI, WebSocket connections, all panel components, three-output view
**Stream C: Data** — Firestore seed script, document processing, pre-load format preparation
**Stream D: Video production** — image generation, video generation, motion graphics, filming planning

---

## Key Technical Decisions for the Orchestrator

1. **ADK vs raw GenAI SDK for conversation agent:** Use ADK. It handles session management, tool orchestration, and the Live API connection. Don't rebuild what ADK gives you.

2. **Synthesizer implementation:** This does NOT need to be an ADK agent. It can be a Python async task that uses the standard Gemini API (not Live API) to process transcript chunks. It runs on a separate async loop from the conversation. Input: latest transcript chunk + current synth JSON. Output: updated synth JSON + new bullets for frontend.

3. **Research agent implementation:** Can be a simple async function triggered by events from the conversation agent or synthesizer. Queries Firestore, formats results, pushes to frontend via WebSocket. Does not need to be a full ADK agent.

4. **Inter-agent communication:** Use an in-memory event bus or simple async queues within the FastAPI process. Don't over-engineer with external message brokers. This is a single-container deployment.

5. **Transcript management:** The full transcript is stored in session state. The synthesizer reads it periodically. The conversation agent does NOT hold the full transcript in its context — it holds the pre-loaded vehicle context + the synthesized JSON summary. This is how we keep the conversation fast even in long sessions.

6. **Frontend state management:** Use React state + WebSocket event handlers. Two WebSocket connections: one for the conversation audio stream, one for context updates (synthesizer bullets, research documents, session state changes). Keep them separate so context updates don't interfere with audio streaming.

7. **Pre-recorded video as webcam input:** Use a Python script that reads a video file and sends frames to the conversation agent at the same rate a real webcam would. The agent processes them identically. This is standard practice for demo environments.

---

## Definition of Done (Demo-Ready)

The demo is ready when all of these work in a single uninterrupted session:

- [ ] Tech starts a session by selecting a 2023 Subaru Outback
- [ ] Repair order info populates at the top
- [ ] Tech speaks naturally and agent responds within 2 seconds
- [ ] Tech asks about CVT TSB, agent responds accurately from pre-loaded context
- [ ] TSB card appears in Related Documents panel
- [ ] Tech says "note that" and a bullet appears in synthesized notes
- [ ] Active Context Panel builds incrementally during conversation
- [ ] Tech says "look at this" and agent identifies what the camera sees
- [ ] Tech says "wrap it up" and three output documents generate
- [ ] All three outputs are accurate, appropriately formatted for their audience, and generated from the session content
- [ ] No errors, no crashes, no hallucinated TSB numbers, no dead air longer than 3 seconds
- [ ] Interruptions handled gracefully (tech talks over agent, agent stops and listens)
