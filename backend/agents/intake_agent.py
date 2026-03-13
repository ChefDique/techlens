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
