"""
Vehicle lookup tool for TechLens.

Queries Firestore `vehicles` collection for make/model/year specs,
common failure modes, and service interval data.
"""

import logging
from typing import Optional

logger = logging.getLogger(__name__)

# Stub data for development / Firestore unavailable fallback
_STUB_VEHICLES = {
    ("2024", "subaru", "outback"): {
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
            "Oil consumption — check PCV breather and piston rings on high-mileage FB25",
            "Head gasket seepage at high mileage (pre-2021 engines more susceptible)",
            "Infotainment (StarLink) freezes — software update via USB",
        ],
        "service_intervals": {
            "oil_change_miles": 6000,
            "transmission_fluid_miles": 30000,
            "spark_plugs_miles": 60000,
            "timing_chain": "No belt — chain driven, inspect at 100k",
        },
        "fluid_specs": {
            "engine_oil": "0W-20 Full Synthetic (API SP / ILSAC GF-6A)",
            "cvt_fluid": "Subaru Lineartronic CVTF II",
            "coolant": "Subaru Super Coolant (blue)",
            "brake_fluid": "DOT 3",
        },
    },
    ("2023", "subaru", "forester"): {
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
            "Oil consumption above 1 qt/1000 mi — piston ring wear on FB25 (pre-2023 TSB 02-157-14)",
            "CVT shudder — CVTF II flush + reprogram",
            "AC compressor clutch failure / refrigerant leak at Schrader valve",
            "Rear wheel bearing noise at 60-80k miles",
            "Windshield stress cracks (EyeSight camera bracket vibration)",
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
    ("2022", "subaru", "crosstrek"): {
        "year": 2022,
        "make": "Subaru",
        "model": "Crosstrek",
        "trim_levels": ["Base", "Premium", "Sport", "Limited"],
        "engine_options": [
            {"code": "FB20D", "displacement": "2.0L", "type": "Boxer-4", "output_hp": 152},
            {"code": "FB25D", "displacement": "2.5L", "type": "Boxer-4", "output_hp": 182},
        ],
        "transmission": "Lineartronic CVT (TR580) or 6MT",
        "awd_system": "Symmetrical AWD",
        "common_issues": [
            "FB20 oil consumption — piston ring recall / warranty extension (WRA-149)",
            "CVT belt wear noise at high mileage on 2.0L",
            "Starter motor failure (single-click no-start) at 40-70k",
            "Brake squeal — front pads glazing, apply Permatex Disc Brake Quiet",
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
}


def lookup_vehicle_info(year: int, make: str, model: str) -> dict:
    """
    Look up vehicle specifications, common issues, and service data.

    Queries the Firestore `vehicles` collection keyed by (year, make, model).
    Falls back to stub data when Firestore is unavailable (development mode).

    Args:
        year: Model year (e.g. 2024)
        make: Vehicle manufacturer (e.g. "Subaru")
        model: Vehicle model name (e.g. "Outback")

    Returns:
        dict with keys: year, make, model, engine_options, transmission,
        awd_system, common_issues, service_intervals, fluid_specs.
        Returns an error dict if the vehicle is not found.
    """
    try:
        from google.cloud import firestore

        db = firestore.Client()
        doc_id = f"{year}_{make.lower()}_{model.lower().replace(' ', '_')}"
        doc_ref = db.collection("vehicles").document(doc_id)
        doc = doc_ref.get()

        if doc.exists:
            logger.info("Vehicle found in Firestore: %s", doc_id)
            return doc.to_dict()

        logger.warning("Vehicle not found in Firestore: %s — falling back to stub", doc_id)

    except Exception as exc:
        logger.warning("Firestore unavailable (%s) — using stub data", exc)

    # Stub fallback
    key = (str(year), make.lower(), model.lower())
    vehicle = _STUB_VEHICLES.get(key)

    if vehicle:
        return vehicle

    return {
        "error": "Vehicle not found",
        "year": year,
        "make": make,
        "model": model,
        "message": (
            f"No data found for {year} {make} {model}. "
            "Consult the OEM service manual directly."
        ),
    }
