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
