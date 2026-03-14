#!/usr/bin/env python3
"""
Migrate techlens_knowledge_base.json to locked schema v1.0.

Changes:
- Add schema_version, ingested_at, type, categories to all documents
- Normalize TSB affected_vehicles to {year_start, year_end, make, models}
- Rename fix -> fix_summary, extract diagnostic_steps
- Normalize parts to {part_number, description, quantity}
- Extract recalls from tsbs[] to top-level recalls[]
- Split complaint component strings into arrays
- Add categories to known_issues_from_field
- Add new fields: special_tools, figures, related_dtcs, cross_references, etc.
- Fix labor_hours on tsb_06-75-22
"""

import json
import re
import copy
from pathlib import Path

INGESTED_AT = "2026-03-14T00:00:00Z"
SCHEMA_VERSION = "1.0"

KB_PATH = Path(__file__).parent.parent / "test_knowledgebase" / "techlens_knowledge_base.json"


# ---------- Category mappings ----------

# Map known issue descriptions to taxonomy categories
KNOWN_ISSUE_CATEGORIES = {
    "windshield": ["VISIBILITY/WIPER"],
    "eyesight": ["FORWARD COLLISION AVOIDANCE"],
    "infotainment": ["ELECTRICAL SYSTEM"],
    "cvt": ["POWER TRAIN"],
    "battery": ["ELECTRICAL SYSTEM"],
    "automatic emergency braking": ["FORWARD COLLISION AVOIDANCE"],
    "false activation": ["FORWARD COLLISION AVOIDANCE"],
    "oil consumption": ["ENGINE"],
    "airbag": ["AIR BAGS"],
    "engine hesitation": ["ENGINE"],
    "stalling": ["ENGINE"],
    "brake squeal": ["SERVICE BRAKES"],
    "rear brake": ["SERVICE BRAKES"],
}

# Map TSB ids to categories
TSB_CATEGORIES = {
    "tsb_02-157-22R": ["POWER TRAIN"],
    "tsb_15-275-21": ["ENGINE"],
    "tsb_11-200-22": ["ELECTRICAL SYSTEM"],
    "tsb_12-235-22": ["FORWARD COLLISION AVOIDANCE"],
    "tsb_11-215-23": ["ELECTRICAL SYSTEM"],
    "tsb_06-75-22": ["ENGINE"],
    "tsb_16-141-21": ["POWER TRAIN"],
    "tsb_02-157-14R": ["ENGINE"],
    "tsb_AC-08-21": ["UNKNOWN OR OTHER"],  # AC is not in taxonomy, closest match
    "tsb_WHL-BRG-03": ["SUSPENSION"],
    "tsb_STR-MOT-01": ["ELECTRICAL SYSTEM"],
    "tsb_BRK-SQK-02": ["SERVICE BRAKES"],
    "tsb_INF-SW-22": ["ELECTRICAL SYSTEM"],
    "tsb_HG-OIL-SEEP-01": ["ENGINE"],
}

# Map TSB ids to severity
TSB_SEVERITY = {
    "tsb_02-157-22R": "MEDIUM",
    "tsb_15-275-21": "HIGH",
    "tsb_11-200-22": "LOW",
    "tsb_12-235-22": "HIGH",
    "tsb_11-215-23": "MEDIUM",
    "tsb_06-75-22": "MEDIUM",
    "tsb_16-141-21": "MEDIUM",
    "tsb_02-157-14R": "MEDIUM",
    "tsb_AC-08-21": "LOW",
    "tsb_WHL-BRG-03": "MEDIUM",
    "tsb_STR-MOT-01": "MEDIUM",
    "tsb_BRK-SQK-02": "LOW",
    "tsb_INF-SW-22": "LOW",
    "tsb_HG-OIL-SEEP-01": "HIGH",
}

# Customer summaries for TSBs
TSB_CUSTOMER_SUMMARIES = {
    "tsb_02-157-22R": "Your transmission may judder at low speeds; a fluid change and software update usually fixes it.",
    "tsb_15-275-21": "The engine's thermal control valve can fail, causing overheating — Subaru extended the warranty to cover this repair.",
    "tsb_11-200-22": "Your infotainment screen may freeze or reboot; a software update should resolve the issue.",
    "tsb_12-235-22": "The EyeSight safety system may intermittently disable; cleaning and software updates usually fix it.",
    "tsb_11-215-23": "Your battery may drain after a few days parked due to a module not sleeping properly; a firmware update can fix this.",
    "tsb_06-75-22": "Your engine may use more oil than expected between changes; Subaru has a test procedure and warranty extension for this.",
    "tsb_16-141-21": "A shudder felt at 25-50 mph under light throttle is usually resolved with a CVT fluid change and software update.",
    "tsb_02-157-14R": "Excessive oil consumption in your engine can be tested and may be covered under an extended warranty program.",
    "tsb_AC-08-21": "Your AC may stop cooling due to a compressor clutch failure or a small refrigerant leak at a service port.",
    "tsb_WHL-BRG-03": "A droning or rumbling noise at highway speed usually means a rear wheel bearing needs replacement.",
    "tsb_STR-MOT-01": "If your engine won't crank or you hear a single click, the starter motor likely needs replacement.",
    "tsb_BRK-SQK-02": "Brake squealing during light stops is typically a noise issue, not a safety concern, and can be corrected with pad service.",
    "tsb_INF-SW-22": "Your touchscreen may freeze or go black; downloading and installing the latest software update usually resolves it.",
    "tsb_HG-OIL-SEEP-01": "Oil or coolant seepage near the cylinder heads is a known issue on older FB25 engines and can be fixed with updated gaskets.",
}

# Related DTCs for applicable TSBs
TSB_RELATED_DTCS = {
    "tsb_02-157-22R": ["P0700", "P0868", "P2764"],
    "tsb_15-275-21": ["P0128", "P0125"],
    "tsb_12-235-22": [],
    "tsb_11-200-22": [],
    "tsb_11-215-23": [],
    "tsb_06-75-22": [],
    "tsb_16-141-21": ["P0700", "P0868", "P2764"],
    "tsb_02-157-14R": [],
    "tsb_AC-08-21": [],
    "tsb_WHL-BRG-03": [],
    "tsb_STR-MOT-01": [],
    "tsb_BRK-SQK-02": [],
    "tsb_INF-SW-22": [],
    "tsb_HG-OIL-SEEP-01": [],
}

# Special tools
TSB_SPECIAL_TOOLS = {
    "tsb_02-157-22R": [],
    "tsb_15-275-21": [],
    "tsb_11-200-22": [],
    "tsb_12-235-22": ["Subaru Select Monitor (SSM)"],
    "tsb_11-215-23": [],
    "tsb_06-75-22": [],
    "tsb_16-141-21": ["Subaru Select Monitor (SSM4)"],
    "tsb_02-157-14R": [],
    "tsb_AC-08-21": ["Manifold gauge set", "UV dye kit", "Electronic leak detector"],
    "tsb_WHL-BRG-03": ["Bearing press"],
    "tsb_STR-MOT-01": [],
    "tsb_BRK-SQK-02": [],
    "tsb_INF-SW-22": [],
    "tsb_HG-OIL-SEEP-01": ["UV dye kit", "Cooling system pressure tester"],
}

# Keywords for TSBs that don't have them
TSB_KEYWORDS_DEFAULTS = {
    "tsb_02-157-22R": ["cvt", "judder", "hesitation", "transmission", "low speed"],
    "tsb_15-275-21": ["thermostat", "thermal control valve", "overheating", "coolant", "check engine light", "TCV"],
    "tsb_11-200-22": ["infotainment", "starlink", "freeze", "reboot", "screen", "blank"],
    "tsb_12-235-22": ["eyesight", "disabled", "camera", "cruise control", "pre-collision"],
    "tsb_11-215-23": ["battery", "drain", "parasitic draw", "DCM", "dead battery", "starlink"],
    "tsb_06-75-22": ["oil", "consumption", "FB25", "low oil", "burning oil"],
}


def parse_string_affected_vehicles(s: str) -> dict:
    """Parse '2020-2023 Outback' or '2023 Outback' into normalized format."""
    # Match patterns like "2020-2023 Outback XT" or "2023 Outback"
    m = re.match(r"(\d{4})(?:-(\d{4}))?\s+(.+)", s)
    if not m:
        return {"year_start": None, "year_end": None, "make": "Subaru", "models": [s]}
    year_start = int(m.group(1))
    year_end = int(m.group(2)) if m.group(2) else year_start
    model = m.group(3).strip()
    return {"year_start": year_start, "year_end": year_end, "make": "Subaru", "models": [model]}


def normalize_affected_vehicles(av_list: list) -> list:
    """Normalize affected_vehicles to standard format."""
    result = []
    for item in av_list:
        if isinstance(item, str):
            result.append(parse_string_affected_vehicles(item))
        elif isinstance(item, dict):
            if "years" in item:
                years = item["years"]
                result.append({
                    "year_start": min(years),
                    "year_end": max(years),
                    "make": item.get("make", "Subaru"),
                    "models": item.get("models", []),
                })
            else:
                # Already in new format or close
                result.append(item)
    return result


def normalize_part(part) -> dict:
    """Normalize a part entry to {part_number, description, quantity}."""
    if isinstance(part, dict):
        # Already an object - ensure field names are correct
        return {
            "part_number": part.get("part_number"),
            "description": part.get("description", ""),
            "quantity": part.get("qty", part.get("quantity", 1)),
        }
    elif isinstance(part, str):
        # Try to parse "SOA868V9350 (CVT Fluid)" pattern
        m = re.match(r"([A-Z0-9]+)\s*\((.+)\)", part)
        if m:
            return {
                "part_number": m.group(1),
                "description": m.group(2),
                "quantity": "As required",
            }
        else:
            return {
                "part_number": None,
                "description": part,
                "quantity": 1,
            }
    return {"part_number": None, "description": str(part), "quantity": 1}


def extract_diagnostic_steps(fix_text: str) -> list:
    """Extract numbered steps from fix text, or create reasonable steps."""
    # Check for numbered steps pattern
    steps = re.findall(r"\d+\.\s*(.+?)(?=\n\d+\.|$)", fix_text, re.DOTALL)
    if steps:
        return [s.strip() for s in steps if s.strip()]

    # No numbered steps - create from the single-sentence fix
    # Split on periods and filter
    sentences = [s.strip() for s in fix_text.split(".") if s.strip()]
    if len(sentences) > 1:
        return [s + "." if not s.endswith(".") else s for s in sentences]
    return [fix_text]


def categorize_known_issue(issue: dict) -> list:
    """Derive categories for a known_issue based on issue name and description."""
    text = (issue.get("issue", "") + " " + issue.get("description", "")).lower()

    for keyword, cats in KNOWN_ISSUE_CATEGORIES.items():
        if keyword in text:
            return cats

    return ["UNKNOWN OR OTHER"]


def derive_vehicle_categories(vehicle: dict) -> list:
    """Derive top-level categories for a vehicle from its complaints and known issues."""
    cats = set()
    # From complaints
    for issue in vehicle.get("nhtsa_complaints", {}).get("top_issues", []):
        for c in issue.get("category", "").split(","):
            c = c.strip()
            if c:
                cats.add(c)
    # From known issues
    for ki in vehicle.get("known_issues_from_field", []):
        for c in categorize_known_issue(ki):
            cats.add(c)
    return sorted(cats)


def migrate_vehicle(vehicle: dict) -> dict:
    """Migrate a vehicle document to schema v1.0."""
    v = copy.deepcopy(vehicle)

    # Add schema fields
    v["schema_version"] = SCHEMA_VERSION
    v["ingested_at"] = INGESTED_AT
    v["type"] = "vehicle"

    # Add categories
    v["categories"] = derive_vehicle_categories(v)

    # Split complaint component strings into arrays
    for issue in v.get("nhtsa_complaints", {}).get("top_issues", []):
        for example in issue.get("examples", []):
            comp = example.get("components", "")
            if isinstance(comp, str) and "," in comp:
                example["components"] = [c.strip() for c in comp.split(",")]
            elif isinstance(comp, str):
                example["components"] = [comp]

    # Add categories to known_issues_from_field
    for ki in v.get("known_issues_from_field", []):
        ki["categories"] = categorize_known_issue(ki)

    # Add schema_version to nested recalls
    for recall in v.get("recalls", []):
        recall["schema_version"] = SCHEMA_VERSION

    return v


def migrate_tsb(tsb: dict) -> dict:
    """Migrate a TSB document to schema v1.0."""
    t = copy.deepcopy(tsb)
    tsb_id = t["id"]

    # Add common fields
    t["schema_version"] = SCHEMA_VERSION
    t["ingested_at"] = INGESTED_AT
    t["source"] = "manufacturer_tsb"

    # Categories
    t["categories"] = TSB_CATEGORIES.get(tsb_id, ["UNKNOWN OR OTHER"])

    # Normalize affected_vehicles
    t["affected_vehicles"] = normalize_affected_vehicles(t.get("affected_vehicles", []))

    # Rename fix -> fix_summary, extract diagnostic_steps
    fix_text = t.pop("fix", "")
    t["fix_summary"] = fix_text
    t["diagnostic_steps"] = extract_diagnostic_steps(fix_text)

    # Normalize parts
    t["parts"] = [normalize_part(p) for p in t.get("parts", [])]

    # Fix labor_hours on tsb_06-75-22
    if tsb_id == "tsb_06-75-22":
        t["labor_hours"] = 0.5
        t["labor_note"] = "15-20 hours for short block replacement if needed"

    # Trim specific
    if tsb_id == "tsb_15-275-21":
        t["trim_specific"] = True
        t["applicable_trims"] = ["Outback XT", "Legacy XT", "Outback Wilderness"]
    else:
        t["trim_specific"] = False
        t["applicable_trims"] = []

    # New fields
    t["special_tools"] = TSB_SPECIAL_TOOLS.get(tsb_id, [])
    t["figures"] = []
    t["related_dtcs"] = TSB_RELATED_DTCS.get(tsb_id, [])
    t["cross_references"] = []
    t["pdf_path"] = None
    t["customer_summary"] = TSB_CUSTOMER_SUMMARIES.get(tsb_id, "")
    t["severity"] = TSB_SEVERITY.get(tsb_id, "MEDIUM")

    # Add keywords where missing
    if "keywords" not in t:
        t["keywords"] = TSB_KEYWORDS_DEFAULTS.get(tsb_id, [])

    return t


def create_top_level_recall(tsb: dict) -> dict:
    """Create a top-level recall from a TSB with type RECALL."""
    # Extract campaign number from id
    campaign = tsb["number"]
    recall_id = f"recall_{campaign}"

    # Normalize affected vehicles
    av = normalize_affected_vehicles(tsb.get("affected_vehicles", []))

    # Determine categories and other fields based on content
    if campaign == "23V647000":
        categories = ["POWER TRAIN"]
        component = "POWER TRAIN:DRIVELINE:DRIVESHAFT"
        summary = "Subaru of America, Inc. (Subaru) is recalling certain 2023 Outback, Legacy, Ascent, and Impreza vehicles. The center support bolts for the driveshaft may loosen, resulting in the disconnection of the front end of the driveshaft."
        consequence = "Separation of the front end of the driveshaft increases the risk of a crash."
        remedy = "Dealers will clean the bolt mounting surfaces of the center support brace and install new bolts, free of charge."
        report_date = "2023-09-21"
        severity = "HIGH"
    elif campaign == "23V755000":
        categories = ["POWER TRAIN"]
        component = "POWER TRAIN:AUTOMATIC TRANSMISSION:PARK/NEUTRAL START INTERLOCK SWITCH"
        summary = "Subaru of America, Inc. is recalling certain model year 2021 Crosstrek, 2022 Forester, 2021-2023 Legacy, and Outback vehicles. An insufficient weld may allow water to enter the inhibitor switch, causing it to fail."
        consequence = "An inoperative inhibitor switch may prevent the reverse lights from illuminating and the rearview camera image from displaying, increasing the risk of a crash."
        remedy = "Dealers will replace the inhibitor switch, free of charge."
        report_date = "2023-11-09"
        severity = "HIGH"
    else:
        categories = ["UNKNOWN OR OTHER"]
        component = ""
        summary = tsb.get("symptom", "")
        consequence = ""
        remedy = tsb.get("fix", "")
        report_date = ""
        severity = "MEDIUM"

    return {
        "schema_version": SCHEMA_VERSION,
        "id": recall_id,
        "type": "recall",
        "categories": categories,
        "campaign_number": campaign,
        "title": tsb["title"],
        "report_date": report_date,
        "affected_vehicles": av,
        "component": component,
        "summary": summary,
        "consequence": consequence,
        "remedy": remedy,
        "cross_references": [],
        "pdf_path": None,
        "severity": severity,
        "source": "nhtsa_recall",
        "ingested_at": INGESTED_AT,
    }


def migrate(data: dict) -> dict:
    """Run the full migration."""
    result = {}

    # Migrate vehicles
    result["vehicles"] = [migrate_vehicle(v) for v in data.get("vehicles", [])]

    # Separate recalls from TSBs, migrate TSBs
    tsbs = []
    top_level_recalls = []
    for tsb in data.get("tsbs", []):
        if tsb.get("type") == "RECALL":
            top_level_recalls.append(create_top_level_recall(tsb))
        else:
            tsbs.append(migrate_tsb(tsb))

    result["tsbs"] = tsbs
    result["recalls"] = top_level_recalls

    # Preserve other top-level keys
    result["diagnostic_tools_required"] = data.get("diagnostic_tools_required", {})
    result["data_sources"] = data.get("data_sources", {})

    return result


def validate(data: dict, original: dict):
    """Validate the migrated data."""
    errors = []

    # Check vehicle count
    if len(data["vehicles"]) != len(original["vehicles"]):
        errors.append(f"Vehicle count mismatch: {len(data['vehicles'])} vs {len(original['vehicles'])}")

    # Check TSB + recall count
    original_tsb_count = len(original["tsbs"])
    recall_count = sum(1 for t in original["tsbs"] if t.get("type") == "RECALL")
    tsb_count = original_tsb_count - recall_count
    if len(data["tsbs"]) != tsb_count:
        errors.append(f"TSB count mismatch: {len(data['tsbs'])} vs expected {tsb_count}")
    if len(data["recalls"]) != recall_count:
        errors.append(f"Recall count mismatch: {len(data['recalls'])} vs expected {recall_count}")

    # Check all vehicles have required fields
    for v in data["vehicles"]:
        for field in ["schema_version", "ingested_at", "type", "categories"]:
            if field not in v:
                errors.append(f"Vehicle {v['id']} missing {field}")
        if v.get("type") != "vehicle":
            errors.append(f"Vehicle {v['id']} type is {v.get('type')}, expected 'vehicle'")
        # Check complaint components are arrays
        for issue in v.get("nhtsa_complaints", {}).get("top_issues", []):
            for ex in issue.get("examples", []):
                if not isinstance(ex.get("components"), list):
                    errors.append(f"Vehicle {v['id']} complaint {ex.get('odi_number')} components not array")
        # Check known issues have categories
        for ki in v.get("known_issues_from_field", []):
            if "categories" not in ki:
                errors.append(f"Vehicle {v['id']} known issue '{ki['issue']}' missing categories")

    # Check all TSBs have required fields
    required_tsb_fields = [
        "schema_version", "ingested_at", "categories", "fix_summary",
        "diagnostic_steps", "trim_specific", "applicable_trims",
        "special_tools", "figures", "related_dtcs", "cross_references",
        "pdf_path", "customer_summary", "severity", "source", "keywords",
    ]
    for t in data["tsbs"]:
        for field in required_tsb_fields:
            if field not in t:
                errors.append(f"TSB {t['id']} missing {field}")
        if "fix" in t:
            errors.append(f"TSB {t['id']} still has 'fix' field (should be 'fix_summary')")
        # Check affected_vehicles normalized
        for av in t.get("affected_vehicles", []):
            if not isinstance(av, dict) or "year_start" not in av:
                errors.append(f"TSB {t['id']} affected_vehicles not normalized: {av}")
        # Check parts normalized
        for p in t.get("parts", []):
            if not isinstance(p, dict) or "quantity" not in p:
                errors.append(f"TSB {t['id']} parts not normalized: {p}")

    # Check tsb_06-75-22 labor_hours fix
    for t in data["tsbs"]:
        if t["id"] == "tsb_06-75-22":
            if t["labor_hours"] != 0.5:
                errors.append(f"tsb_06-75-22 labor_hours should be 0.5, got {t['labor_hours']}")
            if "labor_note" not in t:
                errors.append("tsb_06-75-22 missing labor_note")

    # Check recalls
    required_recall_fields = [
        "schema_version", "id", "type", "categories", "campaign_number",
        "title", "report_date", "affected_vehicles", "component",
        "summary", "consequence", "remedy", "cross_references",
        "pdf_path", "severity", "source", "ingested_at",
    ]
    for r in data["recalls"]:
        for field in required_recall_fields:
            if field not in r:
                errors.append(f"Recall {r.get('id', '?')} missing {field}")

    # Count total complaints to ensure no data loss
    def count_complaints(vehicles):
        total = 0
        for v in vehicles:
            for issue in v.get("nhtsa_complaints", {}).get("top_issues", []):
                total += len(issue.get("examples", []))
        return total

    orig_complaints = count_complaints(original["vehicles"])
    new_complaints = count_complaints(data["vehicles"])
    if orig_complaints != new_complaints:
        errors.append(f"Complaint example count mismatch: {new_complaints} vs {orig_complaints}")

    return errors


def main():
    print(f"Reading KB from {KB_PATH}")
    with open(KB_PATH) as f:
        original = json.load(f)

    print(f"  Vehicles: {len(original['vehicles'])}")
    print(f"  TSBs: {len(original['tsbs'])}")

    migrated = migrate(original)

    print(f"\nAfter migration:")
    print(f"  Vehicles: {len(migrated['vehicles'])}")
    print(f"  TSBs: {len(migrated['tsbs'])}")
    print(f"  Recalls: {len(migrated['recalls'])}")

    errors = validate(migrated, original)
    if errors:
        print(f"\nValidation errors ({len(errors)}):")
        for e in errors:
            print(f"  - {e}")
        return 1
    else:
        print("\nValidation passed!")

    # Write back
    with open(KB_PATH, "w") as f:
        json.dump(migrated, f, indent=2, ensure_ascii=False)
    print(f"\nWrote migrated KB to {KB_PATH}")
    return 0


if __name__ == "__main__":
    exit(main())
