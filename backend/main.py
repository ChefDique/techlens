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
        try:
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
        except Exception as e:
            logger.error("Live agent stream error: %s", e)
            try:
                await ws.send_text(json.dumps({
                    "type": "error",
                    "message": f"Live agent connection lost: {e}",
                }))
            except Exception:
                pass

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
