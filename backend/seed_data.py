"""
TechLens Firestore seed script.

Populates the `vehicles` and `tsbs` collections with realistic
Subaru dealership data for development and demo use.

Usage:
    python seed_data.py              # Write to Firestore
    python seed_data.py --dry-run    # Print data, no writes
"""

import argparse
import json
import sys

# ---------------------------------------------------------------------------
# Seed data
# ---------------------------------------------------------------------------

VEHICLES = [
    {
        "id": "2024_subaru_outback",
        "year": 2024,
        "make": "Subaru",
        "model": "Outback",
        "trim_levels": ["Base", "Premium", "Limited", "Onyx Edition XT", "Touring XT"],
        "engine_options": [
            {"code": "FB25D", "displacement": "2.5L", "type": "Boxer-4", "output_hp": 182},
            {"code": "FA24F", "displacement": "2.4L Turbo", "type": "Boxer-4", "output_hp": 260},
        ],
        "transmission": "Lineartronic CVT (TR580 / TR690 XT)",
        "awd_system": "Symmetrical AWD with active torque vectoring",
        "common_issues": [
            "CVT judder/shudder under light throttle (TSB 16-141-21)",
            "Oil consumption on FB25 at high mileage — check PCV breather",
            "Head gasket seepage pre-2021 engines",
            "StarLink infotainment freeze — USB software update available",
        ],
        "service_intervals": {
            "oil_change_miles": 6000,
            "transmission_fluid_miles": 30000,
            "spark_plugs_miles": 60000,
            "timing_chain": "Chain driven — inspect at 100k",
        },
        "fluid_specs": {
            "engine_oil": "0W-20 Full Synthetic (API SP / ILSAC GF-6A)",
            "cvt_fluid": "Subaru Lineartronic CVTF II",
            "coolant": "Subaru Super Coolant (blue)",
            "brake_fluid": "DOT 3",
        },
    },
    {
        "id": "2023_subaru_forester",
        "year": 2023,
        "make": "Subaru",
        "model": "Forester",
        "trim_levels": ["Base", "Premium", "Sport", "Limited", "Touring"],
        "engine_options": [
            {"code": "FB25D", "displacement": "2.5L", "type": "Boxer-4", "output_hp": 182},
        ],
        "transmission": "Lineartronic CVT (TR580)",
        "awd_system": "Symmetrical AWD",
        "common_issues": [
            "Oil consumption >1 qt/1000 mi — piston ring wear (TSB 02-157-14R)",
            "CVT shudder — CVTF II flush + TCM reprogram",
            "AC compressor clutch failure and Schrader valve refrigerant leak",
            "Rear wheel bearing noise at 60-80k miles",
            "Windshield stress cracks from EyeSight camera bracket vibration",
        ],
        "service_intervals": {
            "oil_change_miles": 6000,
            "transmission_fluid_miles": 30000,
            "spark_plugs_miles": 60000,
            "timing_chain": "Chain driven",
        },
        "fluid_specs": {
            "engine_oil": "0W-20 Full Synthetic",
            "cvt_fluid": "Subaru Lineartronic CVTF II",
            "coolant": "Subaru Super Coolant (blue)",
            "brake_fluid": "DOT 3",
        },
    },
    {
        "id": "2022_subaru_crosstrek",
        "year": 2022,
        "make": "Subaru",
        "model": "Crosstrek",
        "trim_levels": ["Base", "Premium", "Sport", "Limited"],
        "engine_options": [
            {"code": "FB20D", "displacement": "2.0L", "type": "Boxer-4", "output_hp": 152},
            {"code": "FB25D", "displacement": "2.5L", "type": "Boxer-4", "output_hp": 182},
        ],
        "transmission": "Lineartronic CVT (TR580) or 6-speed manual",
        "awd_system": "Symmetrical AWD",
        "common_issues": [
            "FB20 oil consumption — piston ring recall / warranty extension (WRA-149)",
            "CVT belt wear noise on 2.0L at high mileage",
            "Starter motor failure: single-click no-start at 40-70k (TSB-STR-MOT-01)",
            "Front brake squeal — pad glazing, apply Disc Brake Quiet",
            "Door seal water intrusion in heavy rain",
        ],
        "service_intervals": {
            "oil_change_miles": 6000,
            "transmission_fluid_miles": 30000,
            "spark_plugs_miles": 60000,
            "timing_chain": "Chain driven",
        },
        "fluid_specs": {
            "engine_oil": "0W-20 Full Synthetic",
            "cvt_fluid": "Subaru Lineartronic CVTF II",
            "coolant": "Subaru Super Coolant (blue)",
            "brake_fluid": "DOT 3",
        },
    },
]

TSBS = [
    {
        "id": "TSB-16-141-21",
        "title": "CVT Judder / Shudder Under Light Throttle",
        "applies_to": {
            "makes": ["Subaru"],
            "models": ["Outback", "Forester", "Legacy", "Crosstrek"],
            "years": list(range(2019, 2025)),
        },
        "keywords": ["cvt", "judder", "shudder", "vibration", "transmission", "lineartronic"],
        "summary": (
            "Some vehicles may exhibit a shudder/vibration felt through the body during "
            "light throttle acceleration at 25-50 mph. Caused by micro-slippage of the CVT "
            "belt on the primary pulley when fluid is degraded."
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
        "applies_to": {
            "makes": ["Subaru"],
            "models": ["Forester", "Outback", "Crosstrek", "Impreza"],
            "years": list(range(2011, 2023)),
        },
        "keywords": ["oil", "consumption", "burning", "piston", "ring", "blue smoke", "oil level"],
        "summary": (
            "Excessive oil consumption (>1 qt per 1,000 mi). "
            "Root cause is piston ring land wear on FB20/FB25 engines."
        ),
        "procedure": (
            "1. Perform oil consumption test: top off, seal dipstick, drive 1,200 mi.\n"
            "2. If consumption >1 qt/1,200 mi, proceed to piston ring inspection.\n"
            "3. Check PCV system for restriction or failure first.\n"
            "4. Perform compression and leak-down test.\n"
            "5. If rings defective, short block replacement per WM-01000A.\n"
            "6. Extended warranty may apply — check VIN in Subarunet."
        ),
        "parts": [],
        "labor_time_hrs": 0.5,
        "warranty_covered": True,
    },
    {
        "id": "TSB-AC-08-21",
        "title": "AC Compressor Clutch Failure / Refrigerant Leak at Schrader Valve",
        "applies_to": {
            "makes": ["Subaru"],
            "models": ["Forester", "Outback", "Crosstrek"],
            "years": list(range(2018, 2025)),
        },
        "keywords": ["ac", "air conditioning", "compressor", "clutch", "refrigerant", "r134a", "r1234yf", "leak", "schrader", "cooling"],
        "summary": (
            "AC system not cooling. Two failure modes: (1) compressor clutch coil open circuit; "
            "(2) Schrader valve core leak on high-side port."
        ),
        "procedure": (
            "1. Check refrigerant charge with manifold gauge set.\n"
            "2. Inspect Schrader valves with UV dye or electronic leak detector.\n"
            "3. Test clutch coil resistance: spec 3.0-3.6 Ω.\n"
            "4. Measure clutch air gap: spec 0.014–0.026 in.\n"
            "5. Replace Schrader cores if leaking (torque 3 ft-lbs).\n"
            "6. Evacuate and recharge: 2019+ R-1234yf (14.1±1.1 oz)."
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
        "applies_to": {
            "makes": ["Subaru"],
            "models": ["Forester", "Outback", "Crosstrek", "Impreza"],
            "years": list(range(2014, 2025)),
        },
        "keywords": ["wheel bearing", "bearing", "rumble", "hum", "noise", "highway", "rear", "droning"],
        "summary": (
            "Droning or rumbling noise from rear, typically at 45-75 mph, "
            "changing when weaving. Caused by worn rear wheel hub bearing assembly."
        ),
        "procedure": (
            "1. Lift vehicle, spin rear wheels — check for roughness or play.\n"
            "2. On ground, grasp tire at 12/6 o'clock — check for looseness.\n"
            "3. Road test: noise increases loading bad bearing side.\n"
            "4. Remove rear hub, inspect bearing race for spalling/corrosion.\n"
            "5. Press out old bearing, press in new. Torque hub nut to 137 ft-lbs.\n"
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
        "applies_to": {
            "makes": ["Subaru"],
            "models": ["Crosstrek", "Impreza", "Forester"],
            "years": list(range(2013, 2023)),
        },
        "keywords": ["starter", "no start", "no crank", "single click", "solenoid", "won't start", "crank"],
        "summary": (
            "Engine cranks slowly or not at all with a single relay-click. "
            "Battery tests good. Root cause: worn starter motor brushes or failed solenoid contacts."
        ),
        "procedure": (
            "1. Load-test battery: must hold >9.6V under 300A load.\n"
            "2. Voltage drop test on starter circuit: >0.5V drop = resistance issue.\n"
            "3. Apply 12V direct to starter S-terminal — if cranks, issue is upstream.\n"
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
        "applies_to": {
            "makes": ["Subaru"],
            "models": ["Outback", "Forester", "Crosstrek", "Legacy"],
            "years": list(range(2015, 2025)),
        },
        "keywords": ["brake", "squeal", "squeak", "noise", "front", "pad", "rotor"],
        "summary": (
            "High-pitched squeal during light brake application, especially cold. "
            "Caused by glazed OEM pad compound resonating at harmonic frequency."
        ),
        "procedure": (
            "1. Inspect pad thickness: if >4mm and glazed, scuff with 80-grit sandpaper.\n"
            "2. Inspect rotor for scoring or hard spots — resurface or replace.\n"
            "3. Clean caliper slide pins; lubricate with Molykote 111.\n"
            "4. Apply Permatex Disc Brake Quiet to pad backing plates.\n"
            "5. Verify caliper pistons retract freely.\n"
            "6. Road test: 8-10 moderate stops from 40 mph to bed pads/rotors."
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
        "applies_to": {
            "makes": ["Subaru"],
            "models": ["Outback", "Forester", "Legacy", "Crosstrek"],
            "years": list(range(2020, 2025)),
        },
        "keywords": ["infotainment", "starlink", "screen", "freeze", "black screen", "reboot", "software", "update", "navigation"],
        "summary": (
            "Head unit freezes, shows black screen, or reboots randomly. "
            "Resolved by USB software update from mysubaru.com/software."
        ),
        "procedure": (
            "1. Check current version: Settings > System > Software Information.\n"
            "2. Download latest firmware from mysubaru.com/software.\n"
            "3. Copy to blank FAT32 USB drive (max 32GB).\n"
            "4. Insert USB with ignition ON (engine OFF), navigate to Settings > Update Software.\n"
            "5. Do not cycle ignition during update (approx 15-20 min).\n"
            "6. If freeze persists: master reset — hold Power + Nav for 10 sec."
        ),
        "parts": [],
        "labor_time_hrs": 0.5,
        "warranty_covered": True,
    },
    {
        "id": "TSB-HG-OIL-SEEP-01",
        "title": "Head Gasket External Oil / Coolant Seepage — FB25 Pre-2021",
        "applies_to": {
            "makes": ["Subaru"],
            "models": ["Outback", "Forester", "Legacy"],
            "years": list(range(2010, 2021)),
        },
        "keywords": ["head gasket", "seeping", "seepage", "coolant leak", "oil leak", "gasket", "overheating"],
        "summary": (
            "External oil or coolant seepage at head gasket mating surface on FB25 engines. "
            "Early FB25 gaskets used a multi-layer steel design prone to seepage at high mileage. "
            "Updated gasket (revised 2021+) corrects the issue."
        ),
        "procedure": (
            "1. Clean engine thoroughly; apply UV dye to cooling system and oil system.\n"
            "2. Pressure-test cooling system to 13 psi for 15 min — note any drop.\n"
            "3. Road test 15 mi; inspect with UV light for seepage origin.\n"
            "4. If confirmed: remove cylinder heads per WM-01200.\n"
            "5. Install updated head gaskets (part # 11044AA700 R/L).\n"
            "6. Machine check head flatness: max warp 0.002 in per 6 in.\n"
            "7. Torque head bolts in sequence per spec (angle torque method)."
        ),
        "parts": [
            {"part_number": "11044AA700", "description": "Head Gasket Set (updated)", "qty": 1},
        ],
        "labor_time_hrs": 8.5,
        "warranty_covered": False,
    },
]


# ---------------------------------------------------------------------------
# Output helpers
# ---------------------------------------------------------------------------

def print_dry_run():
    """Print all seed data as formatted JSON to stdout."""
    print("\n" + "=" * 60)
    print("DRY RUN — TechLens Firestore Seed Data")
    print("=" * 60)

    print(f"\n--- VEHICLES ({len(VEHICLES)}) ---\n")
    for v in VEHICLES:
        print(json.dumps(v, indent=2, default=str))
        print()

    print(f"\n--- TSBs ({len(TSBS)}) ---\n")
    for tsb in TSBS:
        print(json.dumps(tsb, indent=2, default=str))
        print()

    print(f"Total: {len(VEHICLES)} vehicles, {len(TSBS)} TSBs")
    print("No data was written to Firestore.")


def seed_firestore():
    """Write all seed data to Firestore."""
    try:
        from google.cloud import firestore
    except ImportError:
        print("ERROR: google-cloud-firestore is not installed.")
        print("Run: pip install google-cloud-firestore")
        sys.exit(1)

    db = firestore.Client()

    print(f"Seeding {len(VEHICLES)} vehicles...")
    for vehicle in VEHICLES:
        doc_id = vehicle.pop("id")
        db.collection("vehicles").document(doc_id).set(vehicle)
        vehicle["id"] = doc_id  # restore for reporting
        print(f"  ✓ {doc_id}")

    print(f"\nSeeding {len(TSBS)} TSBs...")
    for tsb in TSBS:
        doc_id = tsb.pop("id")
        db.collection("tsbs").document(doc_id).set(tsb)
        tsb["id"] = doc_id  # restore
        print(f"  ✓ {doc_id}")

    print(f"\nDone. Wrote {len(VEHICLES)} vehicles and {len(TSBS)} TSBs to Firestore.")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Seed TechLens Firestore with Subaru vehicle and TSB data."
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print seed data to stdout without writing to Firestore.",
    )
    args = parser.parse_args()

    if args.dry_run:
        print_dry_run()
    else:
        seed_firestore()
