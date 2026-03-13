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
