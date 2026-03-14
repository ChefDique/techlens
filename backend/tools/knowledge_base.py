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
if not _KB_PATH.exists():
    # Docker layout: /app/test_knowledgebase/
    _KB_PATH = Path("/app/test_knowledgebase/techlens_knowledge_base.json")
_KB = {}

try:
    with open(_KB_PATH) as f:
        _KB = json.load(f)
    logger.info(
        "Knowledge base loaded: %d vehicles, %d TSBs, %d recalls",
        len(_KB.get("vehicles", [])),
        len(_KB.get("tsbs", [])),
        len(_KB.get("recalls", [])),
    )
except FileNotFoundError:
    logger.warning("Knowledge base not found at %s — tools will return empty results", _KB_PATH)


# --- Category normalization ---

_CATEGORY_MAP = {
    "chest clip": "SEAT BELTS",
    "buckle": "SEAT BELTS",
    "harness": "SEAT BELTS",
    "engine and engine cooling": "ENGINE",
}


def normalize_category(raw: str) -> str:
    """Map dirty/variant category names to the fixed taxonomy.

    Known mappings:
      - "Chest Clip", "Buckle", "Harness" -> "SEAT BELTS"
      - "ENGINE AND ENGINE COOLING" -> "ENGINE"

    Anything already in the fixed taxonomy passes through unchanged.
    """
    return _CATEGORY_MAP.get(raw.lower(), raw)


# --- Vehicle matching helper ---

def _vehicle_matches(av: dict, year: int, make: str, model: str) -> bool:
    """Check if an affected_vehicles entry matches the given year/make/model.

    Expects the v1.0 schema format: {year_start, year_end, make, models}.
    """
    return (
        av.get("make", "").lower() == make.lower()
        and model.lower() in [m.lower() for m in av.get("models", [])]
        and av.get("year_start", 0) <= year <= av.get("year_end", 0)
    )


# --- Public API ---

def get_vehicle_profile(year: int, make: str, model: str) -> dict | None:
    """Find a vehicle profile by year/make/model. Returns None if not found."""
    for v in _KB.get("vehicles", []):
        if v["year"] == year and v["make"].lower() == make.lower() and v["model"].lower() == model.lower():
            return v
    return None


def get_matching_tsbs(year: int, make: str, model: str, keywords: list[str] | None = None) -> list[dict]:
    """Find TSBs applicable to a vehicle. Optionally filter by keywords.

    Vehicle matching uses the v1.0 schema: {year_start, year_end, make, models}.
    Keyword filtering checks the TSB's `keywords` array first (exact token match),
    falling back to full-text search if no `keywords` field is present.
    """
    results = []
    for tsb in _KB.get("tsbs", []):
        # Vehicle match
        affected = tsb.get("affected_vehicles", [])
        if not any(_vehicle_matches(av, year, make, model) for av in affected):
            continue

        # Keyword filter (if requested)
        if keywords:
            tsb_keywords = tsb.get("keywords", [])
            if tsb_keywords:
                # Exact match against the TSB's keywords array
                tsb_kw_lower = [k.lower() for k in tsb_keywords]
                if not any(kw.lower() in tsb_kw_lower for kw in keywords):
                    continue
            else:
                # Fallback: full-text search
                tsb_text = json.dumps(tsb).lower()
                if not any(kw.lower() in tsb_text for kw in keywords):
                    continue

        results.append(tsb)
    return results


def get_matching_recalls(year: int, make: str, model: str) -> list[dict]:
    """Find recalls applicable to a vehicle.

    Uses the same {year_start, year_end, make, models} matching as TSBs,
    searching the top-level recalls[] array.
    """
    results = []
    for recall in _KB.get("recalls", []):
        affected = recall.get("affected_vehicles", [])
        if any(_vehicle_matches(av, year, make, model) for av in affected):
            results.append(recall)
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
        dict with matching TSBs, known issues, complaint patterns, and recalls.
    """
    query_tokens = query.lower().split()
    results = {"tsbs": [], "known_issues": [], "complaints": [], "recalls": []}

    # Search TSBs — check keywords array first, fall back to full-text
    for tsb in _KB.get("tsbs", []):
        tsb_keywords = tsb.get("keywords", [])
        matched = False
        if tsb_keywords:
            tsb_kw_lower = [k.lower() for k in tsb_keywords]
            if any(qt in tsb_kw_lower for qt in query_tokens):
                matched = True
        if not matched:
            tsb_text = json.dumps(tsb).lower()
            if any(qt in tsb_text for qt in query_tokens):
                matched = True
        if matched:
            results["tsbs"].append({
                "number": tsb.get("number", ""),
                "title": tsb.get("title", ""),
                "symptom": tsb.get("symptom", tsb.get("description", "")),
                "fix_summary": tsb.get("fix_summary", ""),
                "diagnostic_steps": tsb.get("diagnostic_steps", []),
                "figures": tsb.get("figures", []),
                "pdf_path": tsb.get("pdf_path"),
                "severity": tsb.get("severity", ""),
                "categories": tsb.get("categories", []),
            })

    # Search known issues across all vehicles (or scoped to one)
    for vehicle in _KB.get("vehicles", []):
        if vehicle_id and vehicle.get("id", "") != vehicle_id:
            continue
        for issue in vehicle.get("known_issues_from_field", []):
            issue_text = json.dumps(issue).lower()
            if any(qt in issue_text for qt in query_tokens):
                results["known_issues"].append(issue)

    # Search NHTSA complaints
    for vehicle in _KB.get("vehicles", []):
        if vehicle_id and vehicle.get("id", "") != vehicle_id:
            continue
        for category in vehicle.get("nhtsa_complaints", {}).get("top_issues", []):
            for example in category.get("examples", []):
                if any(qt in example.get("summary", "").lower() for qt in query_tokens):
                    results["complaints"].append({
                        "category": category.get("category", ""),
                        "summary": example.get("summary", "")[:200],
                    })
                    break  # One example per category is enough

    # Search recalls
    for recall in _KB.get("recalls", []):
        recall_text = json.dumps(recall).lower()
        if any(qt in recall_text for qt in query_tokens):
            results["recalls"].append({
                "campaign_number": recall.get("campaign_number", ""),
                "title": recall.get("title", ""),
                "summary": recall.get("summary", ""),
                "remedy": recall.get("remedy", ""),
                "severity": recall.get("severity", ""),
            })

    return results
