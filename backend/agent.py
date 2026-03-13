"""
TechLens ADK agent definition.

Creates and configures the Google ADK LiveRequestQueue-based agent
that powers the TechLens real-time diagnostic assistant.
"""

import logging
import os

from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

SYSTEM_INSTRUCTION = """
You are TechLens, an expert automotive diagnostic assistant.
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
""".strip()

MODEL = "gemini-2.0-flash-live-preview-04-09"


def create_agent():
    """
    Create and return a configured TechLens ADK Agent instance.

    Registers the three TechLens tools:
      - lookup_vehicle_info: fetch vehicle specs and common issues from Firestore
      - search_tsb: find relevant Technical Service Bulletins
      - generate_session_outputs: produce the three end-of-session documents

    Returns:
        google.adk.agents.Agent: Configured agent ready for session use.

    Raises:
        ImportError: If google-adk is not installed.
        Exception: If the ADK agent cannot be initialized.
    """
    from google.adk.agents import Agent

    from tools.vehicle_lookup import lookup_vehicle_info
    from tools.tsb_search import search_tsb
    from tools.output_generator import generate_session_outputs

    agent = Agent(
        model=MODEL,
        name="techlens",
        description="Real-time multimodal automotive diagnostic assistant for service technicians.",
        instruction=SYSTEM_INSTRUCTION,
        tools=[
            lookup_vehicle_info,
            search_tsb,
            generate_session_outputs,
        ],
    )

    logger.info("TechLens ADK agent created (model=%s)", MODEL)
    return agent
