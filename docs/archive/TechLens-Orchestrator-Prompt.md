# Instructions for Coding Agent

## Context

You are working on an EXISTING project called TechLens. The repo is already initialized, has a working prototype with basic Gemini Live API voice conversation, and has been actively developed. DO NOT treat this as a new project. DO NOT scaffold from scratch. DO NOT overwrite existing work. You are evolving what's already here.

The attached document `TechLens-Sprint-Plan-For-Orchestrator.md` is the architectural plan for the next sprint. Read it fully before doing anything. It contains the multi-agent architecture, the build phases, the frontend layout spec, the trigger words system, and the definition of done.

The hackathon deadline is March 16, 2026 @ 5:00 PM PDT. Every decision you make should optimize for a working demo by that deadline.

---

## Step 1: Do This First, Before Anything Else

Run `npm run dev` (or whatever the current dev start command is) and confirm the app boots. Report to Richard:
- What runs successfully
- What errors appear
- What the current state of the frontend looks like
- What the current state of the backend looks like
- What endpoints exist
- What the agent can currently do (voice? text? vision? tools?)

DO NOT change any code in Step 1. This is observation only. Richard needs to test the current form before you touch anything.

---

## Step 2: Audit the Existing Codebase

Before planning any work, understand what exists:
- Map every file in the repo and what it does
- Identify what's functional vs placeholder vs broken
- Identify what dependencies are installed
- Identify how the Gemini Live API connection is currently implemented (raw GenAI SDK? ADK? WebSocket?)
- Identify the current frontend framework and component structure
- Identify the current data layer (Firestore connected? Local mock data? Nothing?)
- Check the current Dockerfile and deployment configuration if any exist

Report your findings as a structured summary. DO NOT start building until Richard approves the audit and the plan.

---

## Step 3: Propose the Work Plan

Based on your audit of what exists and the sprint plan document, create a phased task list. For each task:
- What branch or area of code it affects
- What it depends on (can't start until X is done)
- Estimated complexity (small / medium / large)
- Whether it can be parallelized with other tasks

Organize into parallel work streams where possible:
- Stream A: Backend agents (conversation agent evolution, synthesizer, research agent, FastAPI orchestration)
- Stream B: Frontend (UI components, WebSocket connections, Active Context Panel, three-output view)
- Stream C: Data (Firestore seed script, document processing, pre-load pipeline)

Present this plan to Richard for approval before executing. Richard will approve, modify, or reprioritize.

---

## Step 4: Execution Rules

Once Richard approves the plan, execute tasks according to these rules:

### Branching
- Work in feature branches, not main
- Name branches descriptively: `feat/synthesizer-agent`, `feat/active-context-panel`, `feat/session-preload`
- Merge to main only when a feature is tested and working

### Sub-Agent Task Loops
If you are dispatching work to sub-agents or running iterative build-test cycles:

**Hard rules to prevent infinite loops:**
1. Maximum 5 iterations per task before stopping and reporting to Richard
2. If the same error appears 3 times in a row, STOP. Do not attempt a 4th fix. Report the error with full context and ask Richard for direction.
3. If a task has been running for more than 30 minutes wall-clock time without producing a working result, STOP and report status.
4. If a sub-agent introduces a regression (something that worked before now doesn't), immediately revert and report.
5. Never auto-merge. All merges require Richard's approval.
6. If you're blocked on an external dependency (API key, service not enabled, package not available), STOP and report. Do not try workarounds that change the architecture.

### Testing Between Tasks
- After completing each task, run the dev server and verify:
  - The app still boots without errors
  - Previously working features still work
  - The new feature works as intended
- Report test results to Richard before moving to the next task

### Communication Protocol
- When you complete a task: report what you did, what works, what to test
- When you hit a blocker: report what's blocked, what you tried, what you need
- When you need a decision: present options with tradeoffs, ask Richard to pick
- DO NOT make architectural decisions without Richard's input. The sprint plan is the architecture — follow it. If something in the sprint plan conflicts with the existing codebase, flag it and ask.

---

## What NOT to Do

- DO NOT delete or restructure existing working code without explicit approval
- DO NOT install major new frameworks or libraries without asking first
- DO NOT change the project's package manager, build tool, or deployment target without asking
- DO NOT create a new repo or reinitialize the project
- DO NOT hard-code API keys anywhere
- DO NOT spend time on UI polish before core functionality works
- DO NOT build features not in the sprint plan without asking
- DO NOT attempt to build a general-purpose PDF processing pipeline — for the demo, we pre-process 3-4 specific documents manually
- DO NOT over-engineer inter-agent communication — use in-memory async queues within the single FastAPI process, not external message brokers

---

## Priority Stack (if time runs short, cut from the bottom)

1. Voice conversation works smoothly with pre-loaded vehicle context (NON-NEGOTIABLE)
2. Tool calls return structured data and agent speaks from it (NON-NEGOTIABLE)
3. Live transcript displays in frontend with speaker labels (NON-NEGOTIABLE)
4. Synthesizer agent produces bullet summaries in Active Context Panel (HIGH)
5. Related Documents panel populated by research agent (HIGH)
6. Three-output generation on session end (HIGH)
7. Vision mode responds to "look at this" (MEDIUM)
8. Clickable document popovers in Related Documents (MEDIUM)
9. Pre-recorded video piped as webcam input (MEDIUM)
10. Cloud Run deployment (MEDIUM — do last)
11. Diagram/figure display from TSBs (NICE TO HAVE)
12. History tab on repair order bar (NOT FOR DEMO — visible but inactive)

If we're running out of time on Sunday, items 1-6 are the demo. Items 7-10 make it great. Items 11-12 are future.

---

## Files You Should Read From the Sprint Plan

The sprint plan document contains:
- Multi-agent architecture (conversation, synthesizer, research) — understand the separation of concerns
- Frontend layout spec in ASCII — this is the UI to build
- Session end three-output view spec — this is the payoff screen
- Pre-loading strategy — how vehicle context gets into the agent before conversation starts
- Trigger words table — every phrase the agent responds to and how
- Firestore document design — the shape of the data the tools return
- Agent orchestration pattern — the WebSocket and async loop structure
- Definition of done — the acceptance test checklist

Read all of it. Internalize the architecture. Then audit, plan, and propose.
