"""
Technical Service Bulletin (TSB) search tool for TechLens.

Queries Firestore `tsbs` collection and returns relevant bulletins
matching the vehicle and keyword criteria.
"""

import logging

logger = logging.getLogger(__name__)

# Stub TSB data — realistic Subaru bulletins
_STUB_TSBS = [
    {
        "id": "TSB-16-141-21",
        "title": "CVT Judder / Shudder Under Light Throttle",
        "applies_to": {"makes": ["Subaru"], "models": ["Outback", "Forester", "Legacy", "Crosstrek"], "years": list(range(2019, 2025))},
        "keywords": ["cvt", "judder", "shudder", "vibration", "transmission", "lineartronic"],
        "summary": (
            "Some vehicles may exhibit a shudder/vibration felt through the body during light "
            "throttle acceleration at 25-50 mph. This is caused by micro-slippage of the CVT belt "
            "on the primary pulley when fluid is degraded."
        ),
        "procedure": (
            "1. Verify complaint: test drive, feel for shudder at 25-50 mph under light load.\n"
            "2. Drain and refill CVT fluid with Subaru Lineartronic CVTF II (do NOT flush).\n"
            "3. Reprogram TCM with latest ROM using Subaru Select Monitor (SSM4).\n"
            "4. Test drive to confirm resolution.\n"
            "5. If shudder persists after fluid/reprogram, inspect CVT assembly per WM-00008."
        ),
        "parts": [
            {"part_number": "38325AA140", "description": "Lineartronic CVTF II (1 qt)", "qty": 8},
        ],
        "labor_time_hrs": 1.5,
        "warranty_covered": True,
    },
    {
        "id": "TSB-02-157-14R",
        "title": "Engine Oil Consumption — FB20 / FB25 Piston Ring Inspection",
        "applies_to": {"makes": ["Subaru"], "models": ["Forester", "Outback", "Crosstrek", "Impreza"], "years": list(range(2011, 2023))},
        "keywords": ["oil", "consumption", "burning", "piston", "ring", "blue smoke", "oil level"],
        "summary": (
            "Customer concern of excessive oil consumption (>1 qt per 1,000 mi). "
            "Root cause is piston ring land wear allowing oil past rings into combustion chamber."
        ),
        "procedure": (
            "1. Perform oil consumption test: top off oil, seal dipstick with tape, drive 1,200 mi.\n"
            "2. If consumption >1 qt/1,200 mi, proceed to piston ring inspection.\n"
            "3. Check PCV system for restriction or failure first.\n"
            "4. Perform compression and leak-down test.\n"
            "5. If rings confirmed defective, short block replacement per WM-01000A.\n"
            "6. Extended warranty coverage available — check VIN in Subarunet."
        ),
        "parts": [],
        "labor_time_hrs": 0.5,
        "warranty_covered": True,
    },
    {
        "id": "TSB-A/C-08-21",
        "title": "AC Compressor Clutch Failure / Refrigerant Leak at Schrader Valve",
        "applies_to": {"makes": ["Subaru"], "models": ["Forester", "Outback", "Crosstrek"], "years": list(range(2018, 2025))},
        "keywords": ["ac", "air conditioning", "compressor", "clutch", "refrigerant", "r134a", "r1234yf", "leak", "schrader"],
        "summary": (
            "AC system not cooling. Two common failure modes: (1) compressor clutch coil open circuit "
            "causing no engagement; (2) Schrader valve core leak on high-side port causing refrigerant loss."
        ),
        "procedure": (
            "1. Check refrigerant charge with manifold gauge set.\n"
            "2. Inspect Schrader valves for leaks using UV dye or electronic leak detector.\n"
            "3. If clutch fails to engage: test clutch coil resistance (should be 3.0-3.6 Ω).\n"
            "4. Measure clutch air gap: spec 0.014–0.026 in. Adjust or replace clutch assembly.\n"
            "5. Replace Schrader valve cores if leaking (torque to 3 ft-lbs).\n"
            "6. Evacuate and recharge to spec: 2019+ uses R-1234yf (14.1±1.1 oz)."
        ),
        "parts": [
            {"part_number": "73111FJ000", "description": "AC Compressor Clutch Assembly", "qty": 1},
            {"part_number": "73111SG000", "description": "Schrader Valve Core Set", "qty": 1},
        ],
        "labor_time_hrs": 2.0,
        "warranty_covered": False,
    },
    {
        "id": "TSB-WHL-BRG-03",
        "title": "Rear Wheel Bearing Noise / Rumble at Highway Speed",
        "applies_to": {"makes": ["Subaru"], "models": ["Forester", "Outback", "Crosstrek", "Impreza"], "years": list(range(2014, 2025))},
        "keywords": ["wheel bearing", "bearing", "rumble", "hum", "noise", "highway", "rear"],
        "summary": (
            "Customer reports droning or rumbling noise from rear of vehicle, typically at 45-75 mph. "
            "Noise changes when weaving left/right. Caused by worn rear wheel hub bearing assembly."
        ),
        "procedure": (
            "1. Lift vehicle, spin rear wheels by hand — check for roughness or play.\n"
            "2. With vehicle on ground, grasp tire at 12 and 6 o'clock — check for looseness.\n"
            "3. Road test: noise increases loading bad bearing side (lean away from bad side).\n"
            "4. Remove rear hub assembly. Inspect bearing race for spalling or corrosion.\n"
            "5. Press out old bearing, press in new bearing to hub. Torque hub nut to 137 ft-lbs.\n"
            "6. Recheck ABS reluctor ring alignment before reinstall."
        ),
        "parts": [
            {"part_number": "28373FJ010", "description": "Rear Hub Bearing Assembly", "qty": 1},
        ],
        "labor_time_hrs": 1.5,
        "warranty_covered": False,
    },
    {
        "id": "TSB-STR-MOT-01",
        "title": "No-Crank / Single-Click: Starter Motor Failure",
        "applies_to": {"makes": ["Subaru"], "models": ["Crosstrek", "Impreza", "Forester"], "years": list(range(2013, 2023))},
        "keywords": ["starter", "no start", "no crank", "single click", "solenoid", "won't start"],
        "summary": (
            "Engine cranks slowly or not at all; single relay-click heard from engine bay. "
            "Battery and connections test good. Root cause is worn starter motor brushes or "
            "failed solenoid contacts on high-mileage (40-70k) units."
        ),
        "procedure": (
            "1. Load-test battery: must hold >9.6V under 300A load.\n"
            "2. Voltage drop test on starter circuit: >0.5V drop indicates resistance.\n"
            "3. Apply 12V direct to starter S-terminal — if cranks, issue is upstream circuit.\n"
            "4. If no crank direct: remove starter, bench test. Replace if brushes <4mm.\n"
            "5. Inspect and clean main ground cable at engine block and chassis.\n"
            "6. Torque starter bolts to 37 ft-lbs on reinstall."
        ),
        "parts": [
            {"part_number": "23300AA530", "description": "Starter Motor Assembly", "qty": 1},
        ],
        "labor_time_hrs": 1.0,
        "warranty_covered": False,
    },
    {
        "id": "TSB-BRK-SQK-02",
        "title": "Front Brake Squeal / Squeak on Light Application",
        "applies_to": {"makes": ["Subaru"], "models": ["Outback", "Forester", "Crosstrek", "Legacy"], "years": list(range(2015, 2025))},
        "keywords": ["brake", "squeal", "squeak", "noise", "front", "pad", "rotor"],
        "summary": (
            "High-pitched squeal during light brake application, especially when cold. "
            "Caused by glazed OEM brake pad compound resonating against rotor at harmonic frequency."
        ),
        "procedure": (
            "1. Inspect pad thickness: if >4mm remaining and glazed, scuff with 80-grit sandpaper.\n"
            "2. Inspect rotor surface for scoring or hard spots — resurface or replace if needed.\n"
            "3. Clean caliper slide pins: lubricate with Molykote 111 or equivalent.\n"
            "4. Apply Permatex Disc Brake Quiet or CRC Brake Quiet to pad backing plates.\n"
            "5. Verify caliper pistons retract freely — rebuild or replace seized calipers.\n"
            "6. Road test: perform 8-10 moderate stops from 40 mph to bed new pads/rotors."
        ),
        "parts": [
            {"part_number": "26296FJ000", "description": "Front Brake Pad Set (OEM)", "qty": 1},
        ],
        "labor_time_hrs": 0.8,
        "warranty_covered": False,
    },
    {
        "id": "TSB-INF-SW-22",
        "title": "StarLink Infotainment System Freeze / Black Screen",
        "applies_to": {"makes": ["Subaru"], "models": ["Outback", "Forester", "Legacy", "Crosstrek"], "years": list(range(2020, 2025))},
        "keywords": ["infotainment", "starlink", "screen", "freeze", "black screen", "reboot", "software", "update"],
        "summary": (
            "Head unit freezes, displays black screen, or reboots randomly. "
            "Resolved by software update available via USB or OTA through Subaru Starlink app."
        ),
        "procedure": (
            "1. Check current software version: Settings > System > Software Information.\n"
            "2. Download latest firmware from Subaru's software update portal (mysubaru.com/software).\n"
            "3. Copy update files to blank FAT32 USB drive (max 32GB).\n"
            "4. Insert USB with ignition ON (engine OFF), navigate to Settings > Update Software.\n"
            "5. Do not cycle ignition during update (approx 15-20 min).\n"
            "6. If freeze persists post-update, perform master reset: hold Power + Nav for 10 sec."
        ),
        "parts": [],
        "labor_time_hrs": 0.5,
        "warranty_covered": True,
    },
]


def search_tsb(keywords: str, year: int, make: str, model: str) -> list:
    """
    Search Technical Service Bulletins relevant to a vehicle and symptom keywords.

    Queries the Firestore `tsbs` collection for matching bulletins,
    filtering by vehicle applicability and keyword relevance. Falls back
    to stub data when Firestore is unavailable.

    Args:
        keywords: Space-separated symptom or system keywords (e.g. "cvt shudder vibration")
        year: Vehicle model year (e.g. 2023)
        make: Vehicle manufacturer (e.g. "Subaru")
        model: Vehicle model (e.g. "Forester")

    Returns:
        List of TSB dicts, each containing: id, title, applies_to, summary,
        procedure, parts, labor_time_hrs, warranty_covered.
        Returns an empty list if no matching TSBs are found.
    """
    keyword_list = [kw.lower() for kw in keywords.split()]

    try:
        from google.cloud import firestore

        db = firestore.Client()
        tsbs_ref = db.collection("tsbs")
        query = tsbs_ref.where("applies_to.makes", "array_contains", make)
        results = []

        for doc in query.stream():
            tsb = doc.to_dict()
            applies = tsb.get("applies_to", {})
            if year not in applies.get("years", []):
                continue
            if model not in applies.get("models", []):
                continue
            tsb_keywords = [k.lower() for k in tsb.get("keywords", [])]
            if any(kw in tsb_keywords for kw in keyword_list):
                results.append(tsb)

        if results:
            logger.info("Found %d TSBs in Firestore for %s %s %s", len(results), year, make, model)
            return results

        logger.warning("No TSBs in Firestore — falling back to stub data")

    except Exception as exc:
        logger.warning("Firestore unavailable (%s) — using stub TSB data", exc)

    # Stub fallback: filter by vehicle and keywords
    results = []
    for tsb in _STUB_TSBS:
        applies = tsb.get("applies_to", {})
        if make.lower() not in [m.lower() for m in applies.get("makes", [])]:
            continue
        if year not in applies.get("years", []):
            continue
        if model.lower() not in [m.lower() for m in applies.get("models", [])]:
            continue
        tsb_keywords = [k.lower() for k in tsb.get("keywords", [])]
        if not keyword_list or any(kw in tsb_keywords for kw in keyword_list):
            results.append(tsb)

    logger.info("Stub TSB search returned %d results for %s %s %s", len(results), year, make, model)
    return results
