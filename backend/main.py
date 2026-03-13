"""
TechLens FastAPI application.

Provides:
  GET  /health          — liveness probe for Cloud Run
  WS   /ws/session      — bidirectional WebSocket for Gemini Live sessions
"""

import json
import logging
import os
from contextlib import asynccontextmanager

from dotenv import load_dotenv
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# App lifecycle
# ---------------------------------------------------------------------------

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("TechLens backend starting up")
    yield
    logger.info("TechLens backend shutting down")


app = FastAPI(
    title="TechLens API",
    description="Real-time multimodal AI assistant for auto repair technicians.",
    version="0.1.0",
    lifespan=lifespan,
)

# CORS — wide open for hackathon development; tighten before production
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------------------
# REST endpoints
# ---------------------------------------------------------------------------

@app.get("/health")
async def health_check():
    """Liveness / readiness probe for Cloud Run."""
    return {"status": "ok", "service": "techlens-backend"}


# ---------------------------------------------------------------------------
# WebSocket session handler
# ---------------------------------------------------------------------------

async def send_json(ws: WebSocket, payload: dict):
    """Helper: serialise and send a JSON message over the WebSocket."""
    await ws.send_text(json.dumps(payload))


@app.websocket("/ws/session")
async def session_websocket(websocket: WebSocket):
    """
    Bidirectional WebSocket endpoint for a TechLens diagnostic session.

    Inbound message types (client → server):
      start_session  — begin session with vehicle context
        { type, vehicle: { year, make, model }, ro_number }

      audio          — raw audio chunk from the technician's mic
        { type, data: <base64 audio bytes> }

      video_frame    — camera frame for visual inspection
        { type, data: <base64 JPEG bytes> }

      end_session    — technician has finished; generate outputs
        { type }

    Outbound message types (server → client):
      audio          — Gemini TTS audio response
        { type, data: <base64 audio bytes> }

      transcript     — speech-to-text result
        { type, text: str, role: "user"|"assistant" }

      tool_result    — result of a tool call (TSB lookup, etc.)
        { type, tool: str, result: any }

      session_outputs — the three end-of-session documents
        { type, tech_notes, customer_summary, escalation_brief }

      error          — error notification
        { type, message: str }
    """
    await websocket.accept()
    logger.info("WebSocket connection accepted")

    session_context: dict = {}
    transcript_lines: list = []

    try:
        while True:
            raw = await websocket.receive_text()

            try:
                message = json.loads(raw)
            except json.JSONDecodeError:
                await send_json(websocket, {
                    "type": "error",
                    "message": "Invalid JSON received.",
                })
                continue

            msg_type = message.get("type")

            # ── start_session ────────────────────────────────────────────────
            if msg_type == "start_session":
                vehicle = message.get("vehicle", {})
                ro_number = message.get("ro_number", "")
                session_context = {
                    "vehicle": vehicle,
                    "ro_number": ro_number,
                }
                logger.info(
                    "Session started — RO: %s  Vehicle: %s %s %s",
                    ro_number,
                    vehicle.get("year"),
                    vehicle.get("make"),
                    vehicle.get("model"),
                )

                # TODO: initialise ADK agent session here (Gemini integration)
                # agent = create_agent()
                # runner = Runner(agent=agent, ...)

                await send_json(websocket, {
                    "type": "transcript",
                    "role": "assistant",
                    "text": (
                        f"TechLens ready. I've got a "
                        f"{vehicle.get('year')} {vehicle.get('make')} {vehicle.get('model')} "
                        f"on RO {ro_number}. Looking up vehicle info and TSBs now. "
                        f"What's the customer concern?"
                    ),
                })

            # ── audio ────────────────────────────────────────────────────────
            elif msg_type == "audio":
                audio_data = message.get("data", "")
                logger.debug("Received audio chunk (%d bytes encoded)", len(audio_data))

                # TODO: stream audio bytes to Gemini Live API
                # Stub: echo an acknowledgment transcript
                await send_json(websocket, {
                    "type": "transcript",
                    "role": "user",
                    "text": "[Audio received — Gemini Live integration pending]",
                })

            # ── video_frame ──────────────────────────────────────────────────
            elif msg_type == "video_frame":
                image_data = message.get("data", "")
                logger.debug("Received video frame (%d bytes encoded)", len(image_data))

                # TODO: send frame to Gemini Live for visual inspection
                await send_json(websocket, {
                    "type": "transcript",
                    "role": "assistant",
                    "text": "[Video frame received — visual inspection integration pending]",
                })

            # ── end_session ──────────────────────────────────────────────────
            elif msg_type == "end_session":
                logger.info("Session ending — generating outputs")

                # TODO: call generate_session_outputs via the agent
                # For now, return a stub response
                vehicle = session_context.get("vehicle", {})
                from tools.output_generator import generate_session_outputs

                transcript_text = "\n".join(transcript_lines)
                outputs = generate_session_outputs(
                    transcript=transcript_text,
                    findings=[],
                    vehicle=vehicle,
                )

                await send_json(websocket, {
                    "type": "session_outputs",
                    **outputs,
                })

                logger.info("Session outputs sent — closing WebSocket")
                break

            # ── unknown ──────────────────────────────────────────────────────
            else:
                logger.warning("Unknown message type: %s", msg_type)
                await send_json(websocket, {
                    "type": "error",
                    "message": f"Unknown message type: {msg_type}",
                })

    except WebSocketDisconnect:
        logger.info("WebSocket disconnected by client")
    except Exception as exc:
        logger.exception("Unhandled error in WebSocket session: %s", exc)
        try:
            await send_json(websocket, {
                "type": "error",
                "message": f"Internal server error: {exc}",
            })
        except Exception:
            pass
