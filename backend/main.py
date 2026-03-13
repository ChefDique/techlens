"""
TechLens FastAPI application.

Provides:
  GET  /health              — liveness probe for Cloud Run
  WS   /ws/{user_id}/{sid}  — bidirectional streaming via ADK + Gemini Live API
"""

import asyncio
import base64
import json
import logging
import os
import warnings
from pathlib import Path

# Load .env BEFORE any Google imports so GOOGLE_API_KEY is available
# and we can block ADC from interfering with API-key auth.
from dotenv import load_dotenv

load_dotenv(Path(__file__).parent / ".env")

# Prevent gRPC from picking up stale Application Default Credentials.
# Native audio models use gRPC which calls google.auth.default(), finding
# ~/.config/gcloud/application_default_credentials.json even when we want
# API-key auth. Point GOOGLE_APPLICATION_CREDENTIALS at a non-existent
# file so ADC discovery fails and the SDK falls back to the API key.
if not os.environ.get("GOOGLE_GENAI_USE_VERTEXAI", "").strip() == "1":
    os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = "/dev/null/nonexistent"

from fastapi import FastAPI, WebSocket, WebSocketDisconnect  # noqa: E402
from fastapi.middleware.cors import CORSMiddleware  # noqa: E402
from google.adk.agents.live_request_queue import LiveRequestQueue  # noqa: E402
from google.adk.agents.run_config import RunConfig, StreamingMode  # noqa: E402
from google.adk.runners import Runner  # noqa: E402
from google.adk.sessions import InMemorySessionService  # noqa: E402
from google.genai import types  # noqa: E402

# Import agent after loading env vars (model name may come from env)
from agent import agent  # noqa: E402

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

# Suppress Pydantic serialization warnings from ADK events
warnings.filterwarnings("ignore", category=UserWarning, module="pydantic")

# ---------------------------------------------------------------------------
# Application Initialization (once at startup)
# ---------------------------------------------------------------------------

APP_NAME = "techlens"

app = FastAPI(
    title="TechLens API",
    description="Real-time multimodal AI assistant for auto repair technicians.",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

session_service = InMemorySessionService()
runner = Runner(app_name=APP_NAME, agent=agent, session_service=session_service)


# ---------------------------------------------------------------------------
# REST endpoints
# ---------------------------------------------------------------------------

@app.get("/health")
async def health_check():
    """Liveness / readiness probe for Cloud Run."""
    return {"status": "ok", "service": "techlens-backend"}


# ---------------------------------------------------------------------------
# WebSocket endpoint — ADK bidi-streaming
# ---------------------------------------------------------------------------

@app.websocket("/ws/{user_id}/{session_id}")
async def websocket_endpoint(
    websocket: WebSocket,
    user_id: str,
    session_id: str,
) -> None:
    """Bidirectional streaming WebSocket endpoint for TechLens sessions.

    The frontend sends:
      - JSON text frames: { type: "start_session"|"text"|"end_session", ... }
      - JSON text frames with audio: { type: "audio", data: <base64 PCM 16kHz> }
      - JSON text frames with video: { type: "video_frame", data: <base64 JPEG> }

    The server streams back ADK events (transcripts, audio, tool calls, etc.)
    as JSON text frames.
    """
    await websocket.accept()
    logger.info("WebSocket connected: user=%s session=%s", user_id, session_id)

    # ------------------------------------------------------------------
    # Session Initialization
    # ------------------------------------------------------------------

    # Determine response modality from model name
    model_name = agent.model
    is_native_audio = "native-audio" in model_name.lower()

    if is_native_audio:
        run_config = RunConfig(
            streaming_mode=StreamingMode.BIDI,
            response_modalities=["AUDIO"],
            input_audio_transcription=types.AudioTranscriptionConfig(),
            output_audio_transcription=types.AudioTranscriptionConfig(),
        )
    else:
        # Half-cascade models (like gemini-2.0-flash-live-preview)
        # support both TEXT and AUDIO — default to AUDIO for voice UX
        run_config = RunConfig(
            streaming_mode=StreamingMode.BIDI,
            response_modalities=["AUDIO"],
            input_audio_transcription=types.AudioTranscriptionConfig(),
            output_audio_transcription=types.AudioTranscriptionConfig(),
        )

    # Get or create ADK session
    session = await session_service.get_session(
        app_name=APP_NAME, user_id=user_id, session_id=session_id
    )
    if not session:
        await session_service.create_session(
            app_name=APP_NAME, user_id=user_id, session_id=session_id
        )

    live_request_queue = LiveRequestQueue()

    # ------------------------------------------------------------------
    # Concurrent upstream / downstream tasks
    # ------------------------------------------------------------------

    async def upstream_task() -> None:
        """Receive messages from WebSocket → forward to LiveRequestQueue."""
        while True:
            message = await websocket.receive()

            # Binary frames — raw audio bytes
            if "bytes" in message:
                audio_blob = types.Blob(
                    mime_type="audio/pcm;rate=16000",
                    data=message["bytes"],
                )
                live_request_queue.send_realtime(audio_blob)
                continue

            # Text frames — JSON messages
            if "text" not in message:
                continue

            try:
                msg = json.loads(message["text"])
            except json.JSONDecodeError:
                logger.warning("Received non-JSON text frame, ignoring")
                continue

            msg_type = msg.get("type")

            if msg_type == "start_session":
                # Send vehicle context as the opening text message
                vehicle = msg.get("vehicle", {})
                ro = msg.get("ro_number", "")
                concern = msg.get("customer_concern", "")
                prompt = (
                    f"I'm working on a {vehicle.get('year')} {vehicle.get('make')} "
                    f"{vehicle.get('model')}, RO number {ro}. "
                    f"Customer concern: {concern}. "
                    f"Look up the vehicle info and any relevant TSBs."
                )
                content = types.Content(
                    parts=[types.Part(text=prompt)]
                )
                live_request_queue.send_content(content)

            elif msg_type == "text":
                content = types.Content(
                    parts=[types.Part(text=msg.get("text", ""))]
                )
                live_request_queue.send_content(content)

            elif msg_type == "audio":
                # Base64-encoded PCM audio from frontend
                audio_bytes = base64.b64decode(msg.get("data", ""))
                audio_blob = types.Blob(
                    mime_type="audio/pcm;rate=16000",
                    data=audio_bytes,
                )
                live_request_queue.send_realtime(audio_blob)

            elif msg_type == "video_frame":
                # Base64-encoded JPEG frame from frontend camera
                image_bytes = base64.b64decode(msg.get("data", ""))
                image_blob = types.Blob(
                    mime_type="image/jpeg",
                    data=image_bytes,
                )
                live_request_queue.send_realtime(image_blob)

            elif msg_type == "end_session":
                # Ask the agent to wrap up and generate outputs
                content = types.Content(
                    parts=[types.Part(text=(
                        "The technician is done. Wrap up this session and "
                        "generate the three output documents: tech notes, "
                        "customer summary, and escalation brief."
                    ))]
                )
                live_request_queue.send_content(content)

            else:
                logger.warning("Unknown message type: %s", msg_type)

    async def downstream_task() -> None:
        """Receive ADK events from run_live() → forward to WebSocket."""
        async for event in runner.run_live(
            user_id=user_id,
            session_id=session_id,
            live_request_queue=live_request_queue,
            run_config=run_config,
        ):
            event_json = event.model_dump_json(exclude_none=True, by_alias=True)
            logger.debug("[ADK Event] %s", event_json[:200])
            await websocket.send_text(event_json)

    # Run both tasks concurrently
    try:
        await asyncio.gather(upstream_task(), downstream_task())
    except WebSocketDisconnect:
        logger.info("Client disconnected: user=%s session=%s", user_id, session_id)
    except Exception as e:
        logger.exception("Error in streaming session: %s", e)
    finally:
        live_request_queue.close()
        logger.info("Session closed: user=%s session=%s", user_id, session_id)
