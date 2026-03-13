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
