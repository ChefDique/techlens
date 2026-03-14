# TechLens Reddit Drafts

Copy-paste ready. Post manually from your Reddit account.

---

## Post 1: r/MechanicAdvice

**Flair:** General

**Title:** After 7 years as a Subaru service advisor, I built an AI tool that writes your tech notes while you diagnose — looking for honest feedback

**Body:**

Hey all. I spent 7 years on the service drive at a Subaru dealership. One thing that always killed me was watching our best techs lose 15-20 minutes per RO on documentation. The guy who could hear a bad wheel bearing from across the lot would still be sitting at the computer hunting and pecking his way through tech notes at the end of the day.

So I've been building a side project called TechLens. The basic idea:

- You start a voice conversation with it, describe what's going on — customer complaint, symptoms, whatever
- If you want, you point your phone camera at the component and it can see what you're looking at (leaking gasket, corroded connector, whatever)
- It talks back and walks through diagnosis with you, pulling from TSBs and known complaints for that specific vehicle
- When you're done, it spits out three documents automatically: tech notes formatted for the repair order, a plain-English summary you can hand the customer, and an escalation brief if it needs to go to the manufacturer

Right now the knowledge base only covers three Subaru models (it's what I know), with real TSBs and NHTSA complaint data. It's a working prototype, not a finished product.

I built it for a hackathon, but the reason I picked this problem is because I lived it. I watched advisors try to translate tech-speak for customers and get it wrong. I watched techs skip documentation because it was tedious, then get burned on warranty claims later.

Honest questions for anyone turning wrenches:

- Would you actually use something like this, or is it a solution looking for a problem?
- What's the biggest documentation pain point in your shop right now?
- If an AI assistant was listening while you diagnosed, would that feel helpful or annoying?

Not trying to sell anything. It's a hackathon project. I just want to know if the people who'd actually use this think it's worth pursuing further.

---

## Post 2: r/googledevs

**Flair:** Project / Show & Tell

**Title:** Built a real-time multimodal agent on Gemini Live API with a three-agent pipeline — architecture breakdown and lessons learned

**Body:**

I'm building a project called TechLens for the Gemini Live Agent Challenge hackathon — it's a real-time voice + vision diagnostic assistant for auto repair technicians. Wanted to share the architecture because I ran into some interesting patterns that might be useful to others working with the Live API and ADK.

**The three-agent pipeline:**

Rather than one monolithic agent, I split the work across three specialized agents:

1. **Intake Agent** (gemini-2.5-flash) — Takes vehicle info from a form submission, queries a knowledge base of TSBs and NHTSA complaints, and synthesizes a focused context package. This runs before the live session starts.

2. **Live Agent** (gemini-2.5-flash-native-audio-latest via Gemini Live API) — Handles the real-time bidirectional audio + video stream. This is the one the technician actually talks to. Uses ADK's `LiveRequestQueue` for streaming PCM-16 audio at 16kHz in and 24kHz out, plus JPEG frames at 1 FPS when the camera is active.

3. **Writer Agent** (gemini-2.5-flash) — Takes the session transcript and generates three structured documents post-session.

**The pattern I'm most interested in feedback on: dynamic system instruction injection.**

The knowledge base is about 70KB of JSON (vehicle specs, TSBs, complaint data). Instead of stuffing it all into the system prompt, the Intake Agent pre-filters it down to roughly 2KB of relevant context based on the specific vehicle and reported symptoms. That filtered context then gets injected into the Live Agent's system instructions before the streaming session begins.

This accomplishes two things: the Live Agent stays grounded in real, specific data (TSB numbers, known failure patterns), and you avoid the hallucination problems that come from either (a) dumping too much context or (b) having no grounding data at all.

**Three-state session model:**

The WebSocket orchestrator manages three states — IDLE (connected, no streaming, zero tokens), LISTENING (audio streaming, 15-min cap), and LOOKING (audio + video at 1 FPS, auto-stops after 15 seconds, falls back to LISTENING). This keeps video costs under control while still giving you that "point your camera at it" moment.

**Stack:** Python 3.13, FastAPI, google-adk, google-genai, React 19, Vite, deployed on Cloud Run with Firestore for session persistence.

**Lessons learned so far:**

- Gemini non-deterministically wraps JSON responses in markdown fences. Always strip them before parsing.
- The Live API's native audio model handles conversational turn-taking surprisingly well, but you need to be deliberate about your system instructions to keep responses concise — it defaults to being verbose.
- ADK's `LiveRequestQueue.send_realtime()` for binary blobs vs `send_content()` for text is a distinction that tripped me up initially.

Would love technical feedback, especially from anyone who's worked with the Live API's bidirectional streaming or built multi-agent pipelines with ADK. What would you do differently?

---

## Post 3: r/artificial

**Flair:** Project / Demo

**Title:** Using real-time voice+vision AI for a surprisingly hard domain problem: auto repair diagnostics

**Body:**

Most multimodal AI demos show general-purpose use cases. I wanted to share a project where real-time voice + vision is applied to a specific, messy, real-world domain — auto repair diagnostics — and some of the architectural patterns that emerged.

**The project:** TechLens is a diagnostic copilot for auto mechanics. A technician has a voice conversation with it while diagnosing a vehicle, and can point their phone camera at components for visual context. After the session, it auto-generates documentation for three different audiences from the same conversation: technical notes (for the repair order), a customer-facing summary (plain English), and an escalation brief (for the manufacturer).

It's built on the Gemini Live API for a hackathon, but the interesting parts are the patterns around making multimodal AI actually reliable in a specialized domain.

**Three things I think are worth discussing:**

**1. Context pre-filtering to prevent hallucination**

The knowledge base is 70KB of real data — vehicle specs, Technical Service Bulletins, and 175 actual NHTSA complaints. Feeding all of that into the system prompt is wasteful and counterproductive. Instead, a separate "intake agent" pre-filters the KB down to about 2KB of focused context based on the specific vehicle and symptoms, and that filtered context gets injected into the live agent's system instructions before the session starts. This is essentially a lightweight RAG alternative — deterministic pre-filtering rather than embedding-based retrieval — and it works well when your domain is bounded.

**2. The real-time vision constraint**

Video streaming to an LLM is expensive and mostly redundant (a parked car doesn't change much frame to frame). The system streams camera frames at just 1 FPS as JPEGs and auto-caps video at 15 seconds, then falls back to audio-only. The technician says "let me show you this" — the AI sees the component, incorporates visual context, and the camera turns off. This "burst vision" pattern keeps the interaction natural without burning through tokens on 30 seconds of the same alternator.

**3. Three-audience generation from one conversation**

A single diagnostic conversation contains information needed by three very different audiences: the technician (who needs OEM-formatted notes with part numbers and TSB references), the customer (who needs plain language and cost context), and the manufacturer's warranty team (who needs symptom-to-TSB correlation and failure pattern data). Generating all three from one transcript with a specialized writer agent is a genuine time-saver — in a dealership, this documentation currently happens manually, often by three different people.

**Background:** I spent 7 years as a Subaru service advisor, so this is a problem I watched play out daily. The knowledge base uses real TSBs and real NHTSA complaint data. It's a working prototype deployed on Cloud Run, not a concept deck.

Curious what people think about the context pre-filtering approach vs. traditional RAG for bounded domains, and whether the "burst vision" pattern has legs in other real-time multimodal applications.
