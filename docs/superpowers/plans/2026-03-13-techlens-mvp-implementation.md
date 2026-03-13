# TechLens MVP Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Refactor TechLens from a single-agent Live API demo into a three-agent pipeline (Intake → Live → Writer) with a three-state session model (IDLE/LISTENING/LOOKING) and on-demand camera vision.

**Architecture:** The existing 250-line `main.py` single-agent WebSocket broker becomes a state-machine-driven orchestrator. The existing `agent.py` single agent splits into three focused agents: an Intake agent that pre-filters the knowledge base, a Live agent for real-time voice+vision, and a Writer agent that generates polished documents post-session. The frontend gets an intake loading phase, camera auto-stop, and proper end-session handoff.

**Tech Stack:** Python 3.13, FastAPI, Google ADK (`google-adk`), Google GenAI SDK (`google-genai`), React 19, Vite, Tailwind CSS v4

**Spec:** `docs/superpowers/specs/2026-03-13-techlens-mvp-design.md`

**Existing code to understand before starting:**
- `backend/main.py` — Current single-agent WebSocket broker (250 lines)
- `backend/agent.py` — Current single ADK agent with 3 tools
- `backend/tools/vehicle_lookup.py` — Firestore-with-stub vehicle queries
- `backend/tools/tsb_search.py` — Firestore-with-stub TSB search
- `backend/tools/output_generator.py` — Template stub (no Gemini call)
- `test_knowledgebase/techlens_knowledge_base.json` — 70KB knowledge base
- `frontend/src/App.jsx` — Phase state machine (setup→active→review)
- `frontend/src/components/LiveSession.jsx` — ADK event parsing + audio playback
- `frontend/src/components/SessionStart.jsx` — Vehicle/RO form
- `frontend/src/components/SessionOutputs.jsx` — 3-tab output display
- `frontend/src/components/CameraFeed.jsx` — Camera preview + toggle

---

## Parallel Execution Strategy

Tasks 1-7 (backend) and Tasks 9-10 (frontend) can run as parallel subagent workstreams since the WebSocket message contract is already defined. Task 8 (cleanup) is trivial and can run with either.

- **Backend subagent:** Tasks 1 → 2 → 3 → 4 → 5 → 6 → 7 → 8 (sequential — each builds on the last)
- **Frontend subagent:** Tasks 9 → 10 (sequential — Task 10 modifies files Task 9 touches)
- **Integration:** Task 11 (smoke test) requires both complete
- **Deploy prep:** Tasks 12-13 after integration passes

---

## Chunk 1: Backend Agent Pipeline

### Task 1: Create session state models

**Files:**
- Create: `backend/models/__init__.py`
- Create: `backend/models/session_state.py`

- [ ] **Step 1: Create the models package**

```bash
mkdir -p backend/models
touch backend/models/__init__.py
```

- [ ] **Step 2: Write session state models**

Create `backend/models/session_state.py`:

```python
"""Session state models for the TechLens three-state architecture."""

from enum import Enum
from dataclasses import dataclass, field


class SessionPhase(str, Enum):
    """Three states of a TechLens diagnostic session."""
    IDLE = "idle"           # WebSocket alive, no streaming
    LISTENING = "listening" # Audio streaming to Gemini Live
    LOOKING = "looking"     # Audio + video streaming to Gemini Live


@dataclass
class IntakeContext:
    """Structured context package from the Intake agent."""
    vehicle: dict = field(default_factory=dict)
    relevant_tsbs: list = field(default_factory=list)
    relevant_issues: list = field(default_factory=list)
    complaint_patterns: str = ""
    customer_concern_analysis: str = ""
    suggested_diagnostic_flow: list = field(default_factory=list)
    raw_json: str = ""  # Full JSON string for injection into Live agent prompt


@dataclass
class SessionTranscript:
    """Accumulates transcript entries during a live session."""
    entries: list = field(default_factory=list)  # [{role: str, text: str}]
    findings: list = field(default_factory=list)  # Logged findings from tools

    def add(self, role: str, text: str) -> None:
        self.entries.append({"role": role, "text": text})

    def add_finding(self, description: str, component: str = "", severity: str = "medium") -> None:
        self.findings.append({
            "description": description,
            "component": component,
            "severity": severity,
        })

    def to_text(self) -> str:
        lines = []
        for e in self.entries:
            prefix = "TECH" if e["role"] == "user" else "TECHLENS"
            lines.append(f"[{prefix}] {e['text']}")
        return "\n".join(lines)
```

- [ ] **Step 3: Verify import works**

```bash
cd backend && python -c "from models.session_state import SessionPhase, IntakeContext, SessionTranscript; print('OK')"
```

Expected: `OK`

- [ ] **Step 4: Commit**

```bash
git add backend/models/
git commit -m "feat: add session state models (SessionPhase, IntakeContext, SessionTranscript)"
```

---

### Task 2: Create the unified knowledge base tool

**Files:**
- Create: `backend/tools/knowledge_base.py`

This tool loads `test_knowledgebase/techlens_knowledge_base.json` into memory and provides search functions for both the Intake agent and the Live agent.

- [ ] **Step 1: Write the knowledge base module**

Create `backend/tools/knowledge_base.py`:

```python
"""Unified knowledge base for TechLens.

Loads techlens_knowledge_base.json into memory at import time.
Provides search functions used by both the Intake and Live agents.
"""

import json
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

# Load KB once at import
_KB_PATH = Path(__file__).parent.parent.parent / "test_knowledgebase" / "techlens_knowledge_base.json"
_KB = {}

try:
    with open(_KB_PATH) as f:
        _KB = json.load(f)
    logger.info("Knowledge base loaded: %d vehicles, %d TSBs", len(_KB.get("vehicles", [])), len(_KB.get("tsbs", [])))
except FileNotFoundError:
    logger.warning("Knowledge base not found at %s — tools will return empty results", _KB_PATH)


def get_vehicle_profile(year: int, make: str, model: str) -> dict | None:
    """Find a vehicle profile by year/make/model. Returns None if not found."""
    for v in _KB.get("vehicles", []):
        if v["year"] == year and v["make"].lower() == make.lower() and v["model"].lower() == model.lower():
            return v
    return None


def get_matching_tsbs(year: int, make: str, model: str, keywords: list[str] | None = None) -> list[dict]:
    """Find TSBs applicable to a vehicle. Optionally filter by keywords."""
    results = []
    for tsb in _KB.get("tsbs", []):
        affected = tsb.get("affected_vehicles", [])
        match = any(
            av.get("make", "").lower() == make.lower()
            and model.lower() in [m.lower() for m in av.get("models", [])]
            and year in av.get("years", [])
            for av in affected
        )
        if not match:
            continue
        if keywords:
            tsb_text = json.dumps(tsb).lower()
            if not any(kw.lower() in tsb_text for kw in keywords):
                continue
        results.append(tsb)
    return results


def get_known_issues(year: int, make: str, model: str) -> list[dict]:
    """Get known field issues for a specific vehicle."""
    vehicle = get_vehicle_profile(year, make, model)
    if not vehicle:
        return []
    return vehicle.get("known_issues_from_field", [])


def search_knowledge_base(query: str, vehicle_id: str = "") -> dict:
    """Search the knowledge base for information relevant to a diagnostic query.

    This is the Live agent's tool — called mid-conversation when the agent
    needs data beyond what the Intake agent pre-loaded.

    Args:
        query: Natural language search query (e.g. "CVT shudder at low speed")
        vehicle_id: Optional vehicle ID to scope the search (e.g. "subaru_outback_2023")

    Returns:
        dict with matching TSBs, known issues, and complaint patterns.
    """
    keywords = query.lower().split()
    results = {"tsbs": [], "known_issues": [], "complaints": []}

    # Search TSBs
    for tsb in _KB.get("tsbs", []):
        tsb_text = json.dumps(tsb).lower()
        if any(kw in tsb_text for kw in keywords):
            results["tsbs"].append({
                "number": tsb.get("number", ""),
                "title": tsb.get("title", ""),
                "symptom": tsb.get("symptom", tsb.get("description", "")),
                "fix": tsb.get("fix", ""),
            })

    # Search known issues across all vehicles (or scoped to one)
    for vehicle in _KB.get("vehicles", []):
        if vehicle_id and vehicle.get("id", "") != vehicle_id:
            continue
        for issue in vehicle.get("known_issues_from_field", []):
            issue_text = json.dumps(issue).lower()
            if any(kw in issue_text for kw in keywords):
                results["known_issues"].append(issue)

    # Search NHTSA complaints
    for vehicle in _KB.get("vehicles", []):
        if vehicle_id and vehicle.get("id", "") != vehicle_id:
            continue
        for category in vehicle.get("nhtsa_complaints", {}).get("top_issues", []):
            for example in category.get("examples", []):
                if any(kw in example.get("summary", "").lower() for kw in keywords):
                    results["complaints"].append({
                        "category": category.get("category", ""),
                        "summary": example.get("summary", "")[:200],
                    })
                    break  # One example per category is enough

    return results
```

- [ ] **Step 2: Verify it loads and searches**

```bash
cd backend && python -c "
from tools.knowledge_base import get_vehicle_profile, get_matching_tsbs, search_knowledge_base
v = get_vehicle_profile(2023, 'Subaru', 'Outback')
print(f'Vehicle: {v[\"year\"]} {v[\"make\"]} {v[\"model\"]}' if v else 'NOT FOUND')
r = search_knowledge_base('CVT shudder')
print(f'TSBs found: {len(r[\"tsbs\"])}, Issues: {len(r[\"known_issues\"])}')
"
```

Expected: Vehicle found, at least 1 TSB match

- [ ] **Step 3: Commit**

```bash
git add backend/tools/knowledge_base.py
git commit -m "feat: add unified knowledge base tool with in-memory JSON search"
```

---

### Task 3: Create the Intake agent

**Files:**
- Create: `backend/agents/__init__.py`
- Create: `backend/agents/intake_agent.py`

The Intake agent runs a standard (non-live) Gemini call to analyze the customer concern against the knowledge base and produce a focused context package.

- [ ] **Step 1: Create the agents package**

```bash
mkdir -p backend/agents
touch backend/agents/__init__.py
```

- [ ] **Step 2: Write the Intake agent**

Create `backend/agents/intake_agent.py`:

```python
"""Intake agent for TechLens.

Runs once at session start. Takes vehicle info + customer concern,
queries the knowledge base, and produces a focused context package
that the Live agent uses as its system instruction prefix.
"""

import json
import logging
import os

from google import genai

from tools.knowledge_base import get_vehicle_profile, get_matching_tsbs, get_known_issues

logger = logging.getLogger(__name__)

INTAKE_MODEL = os.getenv("TECHLENS_INTAKE_MODEL", "gemini-2.5-flash")


async def run_intake(year: int, make: str, model: str, ro_number: str, customer_concern: str) -> dict:
    """Run the Intake agent to produce a focused context package.

    Args:
        year: Vehicle model year
        make: Vehicle manufacturer
        model: Vehicle model name
        ro_number: Repair order number
        customer_concern: Customer's stated concern

    Returns:
        dict with keys: vehicle, relevant_tsbs, relevant_issues,
        complaint_patterns, customer_concern_analysis, suggested_diagnostic_flow
    """
    # 1. Query knowledge base
    vehicle = get_vehicle_profile(year, make, model)
    if not vehicle:
        logger.warning("Vehicle not found in KB: %s %s %s", year, make, model)
        vehicle = {"year": year, "make": make, "model": model, "note": "Vehicle not in knowledge base"}

    # Extract keywords from concern for TSB matching
    concern_keywords = customer_concern.lower().split() if customer_concern else []
    tsbs = get_matching_tsbs(year, make, model, keywords=concern_keywords if concern_keywords else None)
    known_issues = get_known_issues(year, make, model)

    # Complaint summary
    nhtsa = vehicle.get("nhtsa_complaints", {})
    complaint_summary = f"{nhtsa.get('total_complaints', 0)} total NHTSA complaints."
    top_issues = nhtsa.get("top_issues", [])
    if top_issues:
        top_str = ", ".join(f"{c['category']} ({c['count']})" for c in top_issues[:5])
        complaint_summary += f" Top: {top_str}"

    # 2. Call Gemini to analyze and synthesize
    kb_context = json.dumps({
        "vehicle": {k: v for k, v in vehicle.items() if k not in ("nhtsa_complaints",)},
        "tsbs": [{"number": t.get("number", ""), "title": t.get("title", ""), "symptom": t.get("symptom", t.get("description", "")), "fix": t.get("fix", "")} for t in tsbs],
        "known_issues": known_issues,
        "customer_concern": customer_concern,
    }, indent=2)

    prompt = f"""You are a senior automotive diagnostic analyst. Given the vehicle data, TSBs, known issues, and customer concern below, produce a JSON analysis.

VEHICLE & KNOWLEDGE BASE DATA:
{kb_context}

Produce a JSON object with these exact keys:
- "customer_concern_analysis": One paragraph analyzing what the customer concern likely indicates, based on the vehicle data and known issues.
- "suggested_diagnostic_flow": A list of 4-6 diagnostic steps the technician should follow, in order.
- "priority_tsbs": List the TSB numbers most relevant to this concern, with a one-line explanation for each.
- "priority_issues": List the known issues most relevant, with a one-line explanation for each.

Return ONLY valid JSON. No markdown fences."""

    try:
        client = genai.Client()
        response = await client.aio.models.generate_content(
            model=INTAKE_MODEL,
            contents=prompt,
        )
        analysis = json.loads(response.text)
    except Exception as e:
        logger.error("Intake Gemini call failed: %s", e)
        analysis = {
            "customer_concern_analysis": f"Customer reports: {customer_concern}",
            "suggested_diagnostic_flow": ["Reproduce the concern", "Visual inspection", "Check for related TSBs"],
            "priority_tsbs": [],
            "priority_issues": [],
        }

    # 3. Build the context package
    context = {
        "vehicle": {
            "id": vehicle.get("id", f"{make.lower()}_{model.lower()}_{year}"),
            "year": year,
            "make": make,
            "model": model,
            "engines": vehicle.get("engines", []),
            "transmission": vehicle.get("transmission", {}),
            "drivetrain": vehicle.get("drivetrain", ""),
            "safety_systems": vehicle.get("safety_systems", []),
        },
        "ro_number": ro_number,
        "customer_concern": customer_concern,
        "relevant_tsbs": tsbs[:5],  # Cap at 5 for context size
        "relevant_issues": known_issues,
        "complaint_patterns": complaint_summary,
        "customer_concern_analysis": analysis.get("customer_concern_analysis", ""),
        "suggested_diagnostic_flow": analysis.get("suggested_diagnostic_flow", []),
        "priority_tsbs": analysis.get("priority_tsbs", []),
        "priority_issues": analysis.get("priority_issues", []),
    }

    logger.info("Intake complete: %d TSBs, %d issues, vehicle=%s %s %s",
                len(context["relevant_tsbs"]), len(context["relevant_issues"]), year, make, model)

    return context
```

- [ ] **Step 3: Quick smoke test**

```bash
cd backend && python -c "
import asyncio
from agents.intake_agent import run_intake
ctx = asyncio.run(run_intake(2023, 'Subaru', 'Outback', 'RO-001', 'noise when turning'))
print(f'Analysis: {ctx[\"customer_concern_analysis\"][:100]}...')
print(f'TSBs: {len(ctx[\"relevant_tsbs\"])}')
print(f'Diagnostic flow: {len(ctx[\"suggested_diagnostic_flow\"])} steps')
"
```

Expected: Analysis text, TSBs found, diagnostic steps listed. If Gemini call fails (no API key in this shell), the fallback should still produce a valid context dict.

- [ ] **Step 4: Commit**

```bash
git add backend/agents/
git commit -m "feat: add Intake agent — pre-filters KB and synthesizes context for Live agent"
```

---

### Task 4: Create the Live agent

**Files:**
- Create: `backend/agents/live_agent.py`

Migrates the existing `agent.py` into the agents package with a dynamic system instruction that incorporates the Intake context.

- [ ] **Step 1: Write the Live agent module**

Create `backend/agents/live_agent.py`:

```python
"""Live agent for TechLens.

The real-time voice + vision diagnostic copilot. Uses Gemini Live API
via ADK for bidirectional audio streaming. System instruction is
dynamically constructed from the Intake agent's context package.
"""

import json
import logging
import os

from google.adk.agents import Agent

from tools.knowledge_base import search_knowledge_base

logger = logging.getLogger(__name__)

LIVE_MODEL = os.getenv("TECHLENS_MODEL", "gemini-2.5-flash-native-audio-latest")

BASE_INSTRUCTION = """You are TechLens, an expert automotive diagnostic copilot assisting a service technician in real time. You speak like a senior master tech — clear, concise, no fluff.

CURRENT SESSION CONTEXT:
{intake_context}

Your behavior:
- You already know the vehicle and its common issues from the context above. Reference them naturally.
- When the tech describes symptoms, correlate with the TSBs and known issues in your context.
- When you see something through the camera, describe what you observe and offer diagnostic recommendations.
- Guide diagnosis step by step, following the suggested diagnostic flow above.
- If the tech asks about something NOT in your current context, use the search_knowledge_base tool.
- When you call search_knowledge_base, include the vehicle ID so results are scoped.
- Track symptoms described, components inspected, findings confirmed, and decisions made.
- When the tech says "wrap it up", "done", or "that's it", give a brief verbal summary of findings.

You are NOT replacing the tech's expertise. You are a hands-free co-pilot that handles reference lookup and keeps track of everything so the tech can focus on the car.

IMPORTANT: Speak naturally and conversationally. Short sentences. No bullet points in speech. Respond to what the tech says, don't lecture."""


def log_finding(description: str, component: str = "", severity: str = "medium") -> dict:
    """Log a diagnostic finding during the session.

    Call this when the technician confirms a finding (e.g. "yep, CV boot is torn").
    These findings are collected for the post-session Tech Notes.

    Args:
        description: What was found (e.g. "Torn CV boot, passenger side, grease on subframe")
        component: Vehicle component (e.g. "CV joint", "brake pads", "transmission")
        severity: How serious: "low", "medium", "high", or "critical"

    Returns:
        Confirmation that the finding was logged.
    """
    logger.info("Finding logged: [%s] %s — %s", severity, component, description)
    return {
        "status": "logged",
        "description": description,
        "component": component,
        "severity": severity,
    }


def create_live_agent(intake_context: dict) -> Agent:
    """Create an ADK Live agent with the Intake context baked into its instruction.

    Args:
        intake_context: The context package from run_intake()

    Returns:
        An ADK Agent configured for live streaming with the session context.
    """
    # Format the context as readable text for the system instruction
    ctx = intake_context
    vehicle = ctx.get("vehicle", {})
    vehicle_str = f"{vehicle.get('year')} {vehicle.get('make')} {vehicle.get('model')}"

    context_text = f"""VEHICLE: {vehicle_str}
RO NUMBER: {ctx.get('ro_number', 'N/A')}
CUSTOMER CONCERN: {ctx.get('customer_concern', 'Not specified')}

ANALYSIS: {ctx.get('customer_concern_analysis', 'No analysis available')}

RELEVANT TSBs:
"""
    for tsb in ctx.get("relevant_tsbs", []):
        context_text += f"- {tsb.get('number', '?')}: {tsb.get('title', '?')} — {tsb.get('symptom', tsb.get('description', ''))}\n"

    context_text += "\nKNOWN ISSUES FOR THIS VEHICLE:\n"
    for issue in ctx.get("relevant_issues", []):
        issue_name = issue.get("issue", issue.get("name", issue.get("title", "Unknown")))
        context_text += f"- {issue_name}\n"

    context_text += f"\nCOMPLAINT PATTERNS: {ctx.get('complaint_patterns', 'None')}\n"

    context_text += "\nSUGGESTED DIAGNOSTIC FLOW:\n"
    for i, step in enumerate(ctx.get("suggested_diagnostic_flow", []), 1):
        context_text += f"{i}. {step}\n"

    instruction = BASE_INSTRUCTION.format(intake_context=context_text)

    agent = Agent(
        model=LIVE_MODEL,
        name="techlens_live",
        description="Real-time multimodal automotive diagnostic copilot.",
        instruction=instruction,
        tools=[search_knowledge_base, log_finding],
    )

    logger.info("Live agent created for %s with %d TSBs, %d issues in context",
                vehicle_str, len(ctx.get("relevant_tsbs", [])), len(ctx.get("relevant_issues", [])))

    return agent
```

- [ ] **Step 2: Verify it creates an agent**

```bash
cd backend && python -c "
from agents.live_agent import create_live_agent
ctx = {'vehicle': {'year': 2023, 'make': 'Subaru', 'model': 'Outback'}, 'relevant_tsbs': [], 'relevant_issues': [], 'customer_concern': 'noise', 'ro_number': 'RO-1'}
agent = create_live_agent(ctx)
print(f'Agent: {agent.name}, model: {agent.model}, tools: {len(agent.tools)}')
"
```

Expected: `Agent: techlens_live, model: gemini-2.5-flash-native-audio-latest, tools: 2`

- [ ] **Step 3: Commit**

```bash
git add backend/agents/live_agent.py
git commit -m "feat: add Live agent with dynamic context injection from Intake"
```

---

### Task 5: Create the Writer agent

**Files:**
- Create: `backend/agents/writer_agent.py`

Replaces the template-based `output_generator.py` with a real Gemini call that generates polished documents.

- [ ] **Step 1: Write the Writer agent**

Create `backend/agents/writer_agent.py`:

```python
"""Writer agent for TechLens.

Runs once after a session ends. Takes the full transcript + intake context
+ logged findings and generates three polished output documents.
"""

import json
import logging
import os
from datetime import datetime, timezone

from google import genai

logger = logging.getLogger(__name__)

WRITER_MODEL = os.getenv("TECHLENS_WRITER_MODEL", "gemini-2.5-flash")

WRITER_PROMPT = """You are a professional automotive documentation writer. Given the session transcript, vehicle info, and diagnostic findings below, generate three documents.

SESSION DATA:
{session_data}

Generate a JSON object with exactly these three keys:

1. "tech_notes": Detailed technical findings for the shop's repair order file. Include:
   - Vehicle info header (year/make/model, RO number)
   - Customer concern (verbatim)
   - Diagnostic procedure performed (numbered steps, based on transcript)
   - Findings (each finding with severity)
   - TSBs referenced (with applicability notes)
   - Recommended repairs (with parts if mentioned and labor estimates)
   Format as clean plain text with headers and line breaks. Professional tone.

2. "customer_summary": Plain-English explanation for the service advisor to share with the customer. Include:
   - What was checked
   - What was found (in non-technical language)
   - What needs to be done and why it matters for safety/reliability
   - Approximate cost range if parts were mentioned
   Friendly, clear, no jargon. 2-3 paragraphs max.

3. "escalation_brief": Structured handoff for manufacturer rep or senior tech. Include:
   - Vehicle and symptom summary
   - Diagnostic steps already performed
   - Findings with severity ratings
   - TSBs checked and applicability
   - Specific question or escalation reason
   Concise, technical, structured with headers.

Return ONLY valid JSON with these three string keys. No markdown fences."""


async def run_writer(transcript_text: str, intake_context: dict, findings: list[dict]) -> dict:
    """Generate the three output documents from session data.

    Args:
        transcript_text: Full session transcript as text
        intake_context: The context package from the Intake agent
        findings: List of logged findings [{description, component, severity}]

    Returns:
        dict with keys: tech_notes, customer_summary, escalation_brief, generated_at
    """
    vehicle = intake_context.get("vehicle", {})
    vehicle_str = f"{vehicle.get('year')} {vehicle.get('make')} {vehicle.get('model')}"

    session_data = json.dumps({
        "vehicle": vehicle_str,
        "ro_number": intake_context.get("ro_number", ""),
        "customer_concern": intake_context.get("customer_concern", ""),
        "transcript": transcript_text,
        "findings": findings,
        "tsbs_referenced": [
            {"number": t.get("number", ""), "title": t.get("title", "")}
            for t in intake_context.get("relevant_tsbs", [])
        ],
    }, indent=2)

    prompt = WRITER_PROMPT.format(session_data=session_data)

    try:
        client = genai.Client()
        response = await client.aio.models.generate_content(
            model=WRITER_MODEL,
            contents=prompt,
        )
        outputs = json.loads(response.text)
    except Exception as e:
        logger.error("Writer Gemini call failed: %s — generating fallback", e)
        outputs = _fallback_outputs(vehicle_str, intake_context, transcript_text, findings)

    outputs["generated_at"] = datetime.now(timezone.utc).isoformat()
    outputs["vehicle_summary"] = vehicle_str

    logger.info("Writer complete: tech_notes=%d chars, customer_summary=%d chars, escalation_brief=%d chars",
                len(outputs.get("tech_notes", "")),
                len(outputs.get("customer_summary", "")),
                len(outputs.get("escalation_brief", "")))

    return outputs


def _fallback_outputs(vehicle_str: str, intake_context: dict, transcript: str, findings: list[dict]) -> dict:
    """Generate basic template outputs when Gemini is unavailable."""
    generated_at = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    findings_text = "\n".join(f"  {i+1}. [{f.get('severity','?')}] {f.get('description','')}" for i, f in enumerate(findings)) or "  No findings logged."

    tech_notes = f"""TECH NOTES — RO# {intake_context.get('ro_number', 'N/A')}
{generated_at}

VEHICLE: {vehicle_str}

CUSTOMER CONCERN:
{intake_context.get('customer_concern', 'Not specified')}

FINDINGS:
{findings_text}

TRANSCRIPT:
{transcript[:2000] if transcript else '[No transcript captured]'}
"""

    customer_summary = f"""SERVICE VISIT SUMMARY
{generated_at}

Vehicle: {vehicle_str}

We inspected your vehicle based on your concern. Our findings:
{findings_text}

Please speak with your service advisor for details and repair recommendations.
"""

    escalation_brief = f"""ESCALATION BRIEF
Vehicle: {vehicle_str} | RO# {intake_context.get('ro_number', 'N/A')}

CONCERN: {intake_context.get('customer_concern', '')}

FINDINGS:
{findings_text}

TRANSCRIPT EXCERPT:
{transcript[:500] if transcript else '[No transcript]'}
"""

    return {
        "tech_notes": tech_notes,
        "customer_summary": customer_summary,
        "escalation_brief": escalation_brief,
    }
```

- [ ] **Step 2: Test the fallback path**

```bash
cd backend && python -c "
import asyncio
from agents.writer_agent import run_writer
result = asyncio.run(run_writer(
    'Tech: CV boot is torn on passenger side. Grease everywhere.',
    {'vehicle': {'year': 2023, 'make': 'Subaru', 'model': 'Outback'}, 'ro_number': 'RO-123', 'customer_concern': 'noise when turning', 'relevant_tsbs': []},
    [{'description': 'Torn CV boot passenger side', 'component': 'CV joint', 'severity': 'high'}]
))
print('Keys:', list(result.keys()))
print('Tech notes preview:', result['tech_notes'][:200])
"
```

Expected: All 3 document keys present, tech notes contain the finding.

- [ ] **Step 3: Commit**

```bash
git add backend/agents/writer_agent.py
git commit -m "feat: add Writer agent — generates 3 polished documents via Gemini post-session"
```

---

### Task 6: Refactor main.py — Three-agent orchestration with state machine

**Files:**
- Modify: `backend/main.py` (full rewrite — the existing 250-line file becomes the three-agent orchestrator)

This is the biggest task. The WebSocket endpoint becomes a state machine that orchestrates Intake → Live → Writer.

- [ ] **Step 1: Write the new main.py**

Replace the contents of `backend/main.py` with the three-agent orchestrator. Key changes from the existing file:

1. Import from `agents/` package instead of `agent.py`
2. Add `intake` phase before starting the Live agent
3. Accumulate transcript during the Live session
4. Run Writer agent on `end_session` instead of asking the Live agent to generate
5. Send `session_outputs` event back to frontend with all 3 documents

```python
"""
TechLens FastAPI application — Three-agent orchestrator.

Provides:
  GET  /health              — liveness probe for Cloud Run
  WS   /ws/{user_id}/{sid}  — bidirectional streaming with Intake → Live → Writer pipeline
"""

import asyncio
import base64
import json
import logging
import os
import warnings
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).parent / ".env")

# Prevent gRPC from picking up stale ADC when using API-key auth.
if not os.environ.get("GOOGLE_GENAI_USE_VERTEXAI", "").strip() == "1":
    os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = "/dev/null/nonexistent"

from fastapi import FastAPI, WebSocket, WebSocketDisconnect  # noqa: E402
from fastapi.middleware.cors import CORSMiddleware  # noqa: E402
from google.adk.agents.live_request_queue import LiveRequestQueue  # noqa: E402
from google.adk.agents.run_config import RunConfig, StreamingMode  # noqa: E402
from google.adk.runners import Runner  # noqa: E402
from google.adk.sessions import InMemorySessionService  # noqa: E402
from google.genai import types  # noqa: E402

from agents.intake_agent import run_intake  # noqa: E402
from agents.live_agent import create_live_agent  # noqa: E402
from agents.writer_agent import run_writer  # noqa: E402
from models.session_state import SessionPhase, SessionTranscript  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger(__name__)
warnings.filterwarnings("ignore", category=UserWarning, module="pydantic")

APP_NAME = "techlens"

app = FastAPI(title="TechLens API", description="Real-time multimodal AI assistant for auto repair technicians.", version="0.2.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])


@app.get("/health")
async def health_check():
    return {"status": "ok", "service": "techlens-backend", "version": "0.2.0"}


@app.websocket("/ws/{user_id}/{session_id}")
async def websocket_endpoint(websocket: WebSocket, user_id: str, session_id: str) -> None:
    """Three-agent pipeline WebSocket endpoint.

    Flow: start_session → Intake agent → Live agent (streaming) → end_session → Writer agent
    """
    await websocket.accept()
    logger.info("WebSocket connected: user=%s session=%s", user_id, session_id)

    phase = SessionPhase.IDLE
    intake_context = None
    transcript = SessionTranscript()
    live_queue = None
    live_events_task = None

    async def send_event(event_type: str, data: dict | None = None):
        """Send a typed JSON event to the frontend."""
        msg = {"type": event_type}
        if data:
            msg.update(data)
        await websocket.send_text(json.dumps(msg))

    async def run_live_downstream(runner: Runner, ws: WebSocket):
        """Receive ADK events from run_live() and forward to WebSocket + transcript."""
        async for event in runner.run_live(
            user_id=user_id,
            session_id=session_id,
            live_request_queue=live_queue,
            run_config=RunConfig(
                streaming_mode=StreamingMode.BIDI,
                response_modalities=["AUDIO"],
                input_audio_transcription=types.AudioTranscriptionConfig(),
                output_audio_transcription=types.AudioTranscriptionConfig(),
            ),
        ):
            # Forward full event to frontend
            event_json = event.model_dump_json(exclude_none=True, by_alias=True)
            await ws.send_text(event_json)

            # Accumulate transcriptions for the Writer agent
            input_t = getattr(event, "input_transcription", None)
            if input_t:
                text = input_t.text if hasattr(input_t, "text") else str(input_t)
                if text and not getattr(input_t, "partial", False):
                    transcript.add("user", text)

            output_t = getattr(event, "output_transcription", None)
            if output_t:
                text = output_t.text if hasattr(output_t, "text") else str(output_t)
                if text and not getattr(output_t, "partial", False):
                    transcript.add("assistant", text)

            # Capture logged findings from tool calls
            if event.content and event.content.parts:
                for part in event.content.parts:
                    fn_resp = getattr(part, "function_response", None)
                    if fn_resp and fn_resp.name == "log_finding":
                        resp_data = fn_resp.response if isinstance(fn_resp.response, dict) else {}
                        if resp_data.get("status") == "logged":
                            transcript.add_finding(
                                description=resp_data.get("description", ""),
                                component=resp_data.get("component", ""),
                                severity=resp_data.get("severity", "medium"),
                            )

    try:
        while True:
            message = await websocket.receive()

            # --- Binary frames: raw audio → Live agent ---
            if "bytes" in message:
                if live_queue and phase in (SessionPhase.LISTENING, SessionPhase.LOOKING):
                    audio_blob = types.Blob(mime_type="audio/pcm;rate=16000", data=message["bytes"])
                    live_queue.send_realtime(audio_blob)
                continue

            if "text" not in message:
                continue

            try:
                msg = json.loads(message["text"])
            except json.JSONDecodeError:
                continue

            msg_type = msg.get("type")

            # --- Start session: run Intake agent ---
            if msg_type == "start_session":
                vehicle = msg.get("vehicle", {})
                await send_event("intake_started")

                try:
                    intake_context = await run_intake(
                        year=int(vehicle.get("year", 0)),
                        make=vehicle.get("make", ""),
                        model=vehicle.get("model", ""),
                        ro_number=msg.get("ro_number", ""),
                        customer_concern=msg.get("customer_concern", ""),
                    )
                    await send_event("intake_complete", {"context": {
                        "customer_concern_analysis": intake_context.get("customer_concern_analysis", ""),
                        "suggested_diagnostic_flow": intake_context.get("suggested_diagnostic_flow", []),
                        "tsb_count": len(intake_context.get("relevant_tsbs", [])),
                        "issue_count": len(intake_context.get("relevant_issues", [])),
                    }})
                except Exception as e:
                    logger.error("Intake agent failed: %s", e)
                    intake_context = {
                        "vehicle": vehicle,
                        "ro_number": msg.get("ro_number", ""),
                        "customer_concern": msg.get("customer_concern", ""),
                        "relevant_tsbs": [],
                        "relevant_issues": [],
                    }
                    await send_event("intake_complete", {"context": {"error": str(e)}})

                # Create Live agent with intake context and start streaming
                live_agent = create_live_agent(intake_context)
                session_service = InMemorySessionService()
                runner = Runner(app_name=APP_NAME, agent=live_agent, session_service=session_service)

                session = await session_service.get_session(app_name=APP_NAME, user_id=user_id, session_id=session_id)
                if not session:
                    await session_service.create_session(app_name=APP_NAME, user_id=user_id, session_id=session_id)

                live_queue = LiveRequestQueue()
                live_events_task = asyncio.create_task(run_live_downstream(runner, websocket))
                phase = SessionPhase.LISTENING
                logger.info("Live agent started, phase=LISTENING")

            # --- Text message to Live agent ---
            elif msg_type == "text":
                if live_queue and phase != SessionPhase.IDLE:
                    content = types.Content(parts=[types.Part(text=msg.get("text", ""))])
                    live_queue.send_content(content)

            # --- Audio (base64 fallback path) ---
            elif msg_type == "audio":
                if live_queue and phase != SessionPhase.IDLE:
                    audio_bytes = base64.b64decode(msg.get("data", ""))
                    audio_blob = types.Blob(mime_type="audio/pcm;rate=16000", data=audio_bytes)
                    live_queue.send_realtime(audio_blob)

            # --- Video frame ---
            elif msg_type == "video_frame":
                if live_queue and phase in (SessionPhase.LISTENING, SessionPhase.LOOKING):
                    image_bytes = base64.b64decode(msg.get("data", ""))
                    image_blob = types.Blob(mime_type="image/jpeg", data=image_bytes)
                    live_queue.send_realtime(image_blob)
                    if phase == SessionPhase.LISTENING:
                        phase = SessionPhase.LOOKING
                        logger.info("Phase transition: LISTENING → LOOKING")

            # --- Camera stopped ---
            elif msg_type == "camera_stopped":
                if phase == SessionPhase.LOOKING:
                    phase = SessionPhase.LISTENING
                    logger.info("Phase transition: LOOKING → LISTENING")

            # --- End session: close Live agent, run Writer ---
            elif msg_type == "end_session":
                logger.info("End session requested")
                await send_event("generating_outputs")

                # Close the Live agent
                if live_queue:
                    live_queue.close()
                if live_events_task:
                    try:
                        await asyncio.wait_for(live_events_task, timeout=5.0)
                    except (asyncio.TimeoutError, Exception):
                        live_events_task.cancel()

                phase = SessionPhase.IDLE

                # Run Writer agent
                try:
                    outputs = await run_writer(
                        transcript_text=transcript.to_text(),
                        intake_context=intake_context or {},
                        findings=transcript.findings,
                    )
                    await send_event("session_outputs", {"outputs": outputs})
                except Exception as e:
                    logger.error("Writer agent failed: %s", e)
                    await send_event("session_outputs", {"outputs": {
                        "tech_notes": f"Error generating outputs: {e}",
                        "customer_summary": "",
                        "escalation_brief": "",
                    }})

            else:
                logger.warning("Unknown message type: %s", msg_type)

    except WebSocketDisconnect:
        logger.info("Client disconnected: user=%s session=%s", user_id, session_id)
    except Exception as e:
        logger.exception("Session error: %s", e)
    finally:
        if live_queue:
            live_queue.close()
        if live_events_task and not live_events_task.done():
            live_events_task.cancel()
        logger.info("Session closed: user=%s session=%s", user_id, session_id)
```

- [ ] **Step 2: Verify server starts**

```bash
cd backend && python -c "from main import app; print(f'Routes: {[r.path for r in app.routes]}')"
```

Expected: Routes include `/health` and `/ws/{user_id}/{session_id}`

- [ ] **Step 3: Commit**

```bash
git add backend/main.py
git commit -m "refactor: main.py → three-agent orchestrator with state machine"
```

---

### Task 7: Clean up old agent.py

**Files:**
- Modify: `backend/agent.py` (replace with re-export for backwards compatibility during transition)

- [ ] **Step 1: Replace agent.py with deprecation shim**

Replace `backend/agent.py` contents with:

```python
"""DEPRECATED — TechLens agent definitions have moved to agents/ package.

This file exists only for backwards compatibility during transition.
Import from agents.live_agent instead.
"""

# Re-export for any code that still imports from here
from agents.live_agent import create_live_agent  # noqa: F401
```

- [ ] **Step 2: Commit**

```bash
git add backend/agent.py
git commit -m "refactor: deprecate root agent.py, point to agents/ package"
```

---

## Chunk 2: Frontend Updates

### Task 8: Delete deprecated output_generator.py

**Files:**
- Delete: `backend/tools/output_generator.py`

- [ ] **Step 1: Remove the file**

```bash
rm backend/tools/output_generator.py
```

- [ ] **Step 2: Commit**

```bash
git add -u backend/tools/output_generator.py
git commit -m "chore: remove output_generator.py (replaced by Writer agent)"
```

---

### Task 9: Update SessionStart year default

**Files:**
- Modify: `frontend/src/components/SessionStart.jsx:11`

- [ ] **Step 1: Change default year to 2023**

In `frontend/src/components/SessionStart.jsx`, line 11, change:
```javascript
    year: '2024',
```
to:
```javascript
    year: '2023',
```

- [ ] **Step 2: Commit**

```bash
git add frontend/src/components/SessionStart.jsx
git commit -m "fix: default year to 2023 to match knowledge base vehicles"
```

---

### Task 10: Update LiveSession + CameraFeed — Intake phase, camera auto-stop with countdown, Writer handoff

**Files:**
- Modify: `frontend/src/components/LiveSession.jsx`
- Modify: `frontend/src/components/CameraFeed.jsx`

This task combines all frontend LiveSession and CameraFeed changes into one to avoid conflicting edits to `handleCameraToggle`.

**Changes to LiveSession.jsx:**

1. Add intake loading state + context display
2. Handle orchestrator events (intake_started, intake_complete, generating_outputs, session_outputs)
3. Camera auto-stop with 15s countdown
4. `camera_stopped` message to backend
5. Clean `handleEndSession` (backend sends generating_outputs event now)

- [ ] **Step 1: Add new state declarations**

After line 105 (`const [isEnding, setIsEnding] = useState(false)`), add:
```javascript
  const [intakeStatus, setIntakeStatus] = useState('pending') // 'pending' | 'loading' | 'ready'
  const [intakeContext, setIntakeContext] = useState(null)
  const [cameraCountdown, setCameraCountdown] = useState(null)
  const cameraTimerRef = useRef(null)
  const countdownIntervalRef = useRef(null)
```

- [ ] **Step 2: Add orchestrator event handlers**

In the event processing `useEffect` (starts at line 137), add this BEFORE `const parsed = parseAdkEvent(lastEvent)` (line 140):

```javascript
    // Handle orchestrator events (not ADK events)
    if (lastEvent.type === 'intake_started') {
      setIntakeStatus('loading')
      return
    }
    if (lastEvent.type === 'intake_complete') {
      setIntakeStatus('ready')
      setIntakeContext(lastEvent.context)
      return
    }
    if (lastEvent.type === 'generating_outputs') {
      setIsEnding(true)
      setTranscript((prev) => [...prev, {
        role: 'assistant',
        text: 'Generating session documents...',
        id: Date.now(),
      }])
      return
    }
    if (lastEvent.type === 'session_outputs') {
      onEnd(lastEvent.outputs)
      return
    }
```

- [ ] **Step 3: Replace handleCameraToggle with auto-stop + countdown version**

Replace the existing `handleCameraToggle` function (lines 223-229) with:

```javascript
  function handleCameraToggle() {
    if (isCameraActive) {
      stopCamera()
      sendMessage({ type: 'camera_stopped' })
      setCameraCountdown(null)
      if (cameraTimerRef.current) {
        clearTimeout(cameraTimerRef.current)
        cameraTimerRef.current = null
      }
      if (countdownIntervalRef.current) {
        clearInterval(countdownIntervalRef.current)
        countdownIntervalRef.current = null
      }
    } else {
      startCamera()
      setCameraCountdown(15)
      countdownIntervalRef.current = setInterval(() => {
        setCameraCountdown((prev) => {
          if (prev <= 1) {
            clearInterval(countdownIntervalRef.current)
            countdownIntervalRef.current = null
            return null
          }
          return prev - 1
        })
      }, 1000)
      cameraTimerRef.current = setTimeout(() => {
        stopCamera()
        sendMessage({ type: 'camera_stopped' })
        setCameraCountdown(null)
        if (countdownIntervalRef.current) {
          clearInterval(countdownIntervalRef.current)
          countdownIntervalRef.current = null
        }
        cameraTimerRef.current = null
      }, 15000)
    }
  }
```

- [ ] **Step 4: Replace handleEndSession**

Replace the existing `handleEndSession` function (lines 231-242) with:

```javascript
  function handleEndSession() {
    setIsEnding(true)
    stopAudio()
    stopCamera()
    setIsMicActive(false)
    sendMessage({ type: 'end_session' })
  }
```

- [ ] **Step 5: Add cleanup effect**

Add after the auto-scroll useEffect:
```javascript
  useEffect(() => {
    return () => {
      if (cameraTimerRef.current) clearTimeout(cameraTimerRef.current)
      if (countdownIntervalRef.current) clearInterval(countdownIntervalRef.current)
    }
  }, [])
```

- [ ] **Step 6: Add intake overlay to JSX**

The component's return JSX starts with `<div className="h-full flex flex-col...">`. Wrap the content: add this as the FIRST child inside that outer div, before the left panel:

```jsx
      {intakeStatus !== 'ready' && (
        <div className="absolute inset-0 bg-gray-900/90 z-10 flex items-center justify-center">
          <div className="text-center">
            <div className="animate-spin w-10 h-10 border-4 border-blue-500 border-t-transparent rounded-full mx-auto mb-4" />
            <p className="text-lg text-white">Analyzing vehicle data...</p>
            <p className="text-sm text-gray-400 mt-1">Preparing diagnostic context</p>
          </div>
        </div>
      )}
```

Also add `relative` to the outer div's className: `"h-full flex flex-col lg:flex-row gap-0 overflow-hidden relative"`

- [ ] **Step 7: Add intake context summary**

After the status indicators `<div>` (the one with Connection/Recording/Camera), add:

```jsx
        {intakeContext && !intakeContext.error && (
          <div className="bg-gray-800 rounded-xl px-5 py-3 border border-gray-700 text-sm text-gray-300">
            <div className="font-medium text-white mb-1">Session Ready</div>
            <div>{intakeContext.tsb_count} TSBs loaded, {intakeContext.issue_count} known issues</div>
          </div>
        )}
```

- [ ] **Step 8: Pass countdown to CameraFeed**

Change the `<CameraFeed>` JSX to:
```jsx
        <CameraFeed
          isActive={isCameraActive}
          onToggle={handleCameraToggle}
          stream={cameraStream}
          autoStopSeconds={cameraCountdown}
        />
```

**Changes to CameraFeed.jsx:**

- [ ] **Step 9: Update CameraFeed props and add countdown display**

Change the component signature (line 3) from:
```jsx
export default function CameraFeed({ onFrame, isActive, onToggle, stream }) {
```
to:
```jsx
export default function CameraFeed({ isActive, onToggle, stream, autoStopSeconds = null }) {
```

Note: `onFrame` is unused in this component (frame capture happens in `useCameraStream` hook). Removing it is intentional.

After the LIVE status badge (line 40), add:
```jsx
        {isActive && autoStopSeconds !== null && (
          <div className="absolute top-3 right-3 bg-black/60 px-2.5 py-1 rounded-full text-xs text-yellow-400 font-mono">
            {autoStopSeconds}s
          </div>
        )}
```

- [ ] **Step 10: Verify frontend builds**

```bash
cd frontend && npm run build
```

Expected: Build succeeds with no errors.

- [ ] **Step 11: Commit**

```bash
git add frontend/src/components/LiveSession.jsx frontend/src/components/CameraFeed.jsx
git commit -m "feat: intake loading phase, 15s camera auto-stop with countdown, writer handoff"
```

---

## Chunk 3: Integration Testing & Deployment Prep

### Task 11: End-to-end smoke test

**Files:** None (testing only)

- [ ] **Step 1: Start the backend**

```bash
cd backend && source .venv/bin/activate && uvicorn main:app --reload --port 8080
```

Expected: Server starts, logs "Knowledge base loaded: 3 vehicles, 8 TSBs"

- [ ] **Step 2: Start the frontend**

```bash
cd frontend && npm run dev
```

Expected: Vite dev server on localhost:5173

- [ ] **Step 3: Test the full flow**

Open the app in Chrome:
1. Fill in: 2023 Subaru Outback, RO-TEST-001, "clicking noise when turning"
2. Click Start Session
3. Verify: "Analyzing vehicle data..." overlay appears
4. Verify: Overlay disappears, "Session Ready" shows TSB count
5. Enable mic, speak
6. Verify: Agent responds with audio, references the vehicle
7. Tap camera, verify 15s countdown
8. Camera auto-stops
9. Click End Session
10. Verify: Tech Notes, Customer Summary, Escalation Brief appear in tabs

- [ ] **Step 4: Fix any issues found during testing**

Document and fix.

- [ ] **Step 5: Commit any fixes**

```bash
git add -A && git commit -m "fix: integration test fixes"
```

---

### Task 12: Update Dockerfile and deploy script

**Files:**
- Modify: `backend/Dockerfile`
- Review: `deploy.sh`

- [ ] **Step 1: Update Dockerfile to copy knowledge base**

The Dockerfile is in `backend/` but the knowledge base is at `test_knowledgebase/` (sibling directory). Docker COPY cannot reference parent directories. Solution: change build context to project root.

Update `backend/Dockerfile`:
```dockerfile
FROM python:3.12-slim

WORKDIR /app

# Install dependencies
COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy backend source
COPY backend/ .

# Copy knowledge base for in-memory loading
COPY test_knowledgebase/ /app/test_knowledgebase/

EXPOSE 8080
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8080"]
```

Also update `knowledge_base.py` path resolution to check both relative locations:
```python
# In knowledge_base.py, update _KB_PATH to check Docker layout too:
_KB_PATH = Path(__file__).parent.parent.parent / "test_knowledgebase" / "techlens_knowledge_base.json"
if not _KB_PATH.exists():
    # Docker layout: /app/test_knowledgebase/
    _KB_PATH = Path("/app/test_knowledgebase/techlens_knowledge_base.json")
```

- [ ] **Step 2: Verify Docker build from project root**

```bash
cd /Users/richardadair/ai_projects/techlens && docker build -f backend/Dockerfile -t techlens-backend .
```

- [ ] **Step 3: Commit**

```bash
git add backend/Dockerfile
git commit -m "build: update Dockerfile to include knowledge base"
```

---

### Task 13: Update README

**Files:**
- Modify: `README.md`

- [ ] **Step 1: Update README with new architecture**

Update the README to reflect the three-agent pipeline, the three-state session model, and spin-up instructions. This is a contest deliverable.

- [ ] **Step 2: Commit**

```bash
git add README.md
git commit -m "docs: update README with three-agent architecture and spin-up instructions"
```
