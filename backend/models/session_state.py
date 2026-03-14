"""Session state models for the TechLens three-state architecture."""

from __future__ import annotations

from enum import Enum
from dataclasses import dataclass, field
from datetime import datetime, timezone


class SessionPhase(str, Enum):
    """Three states of a TechLens diagnostic session."""
    IDLE = "idle"           # WebSocket alive, no streaming
    LISTENING = "listening" # Audio streaming to Gemini Live
    LOOKING = "looking"     # Audio + video streaming to Gemini Live


@dataclass
class IntakeContext:
    """Structured context package from the Intake agent."""
    vehicle: dict = field(default_factory=dict)
    relevant_tsbs: list = field(default_factory=list)
    relevant_issues: list = field(default_factory=list)
    complaint_patterns: str = ""
    customer_concern_analysis: str = ""
    suggested_diagnostic_flow: list = field(default_factory=list)
    raw_json: str = ""  # Full JSON string for injection into Live agent prompt


@dataclass
class SessionTranscript:
    """Accumulates transcript entries during a live session."""
    entries: list = field(default_factory=list)  # [{role: str, text: str, timestamp: str}]
    findings: list = field(default_factory=list)  # Logged findings from tools

    def add(self, role: str, text: str) -> None:
        self.entries.append({
            "role": role,
            "text": text,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })

    def add_finding(self, description: str, component: str = "", severity: str = "medium") -> None:
        self.findings.append({
            "description": description,
            "component": component,
            "severity": severity,
        })

    def to_text(self) -> str:
        lines = []
        for e in self.entries:
            prefix = "TECH" if e["role"] == "user" else "TECHLENS"
            lines.append(f"[{prefix}] {e['text']}")
        return "\n".join(lines)


@dataclass
class SessionSynthesis:
    """Layer 2 synthesizer output — structured findings from the live session."""
    findings: list = field(default_factory=list)
    # Each finding: {"description": str, "categories": list[str], "severity": "L1"|"L2"|"L3", "source_tsb": str|None}
    referenced_documents: list[str] = field(default_factory=list)  # IDs of Layer 1 docs surfaced
    open_items: list[str] = field(default_factory=list)            # Items still unresolved
    blocking_issues: list[str] = field(default_factory=list)       # Items blocking diagnosis

    def add_finding(
        self,
        description: str,
        categories: list[str],
        severity: str,
        source_tsb: str | None = None,
    ) -> None:
        self.findings.append({
            "description": description,
            "categories": categories,
            "severity": severity,
            "source_tsb": source_tsb,
        })

    def add_document_reference(self, doc_id: str) -> None:
        if doc_id not in self.referenced_documents:
            self.referenced_documents.append(doc_id)

    def to_dict(self) -> dict:
        return {
            "findings": self.findings,
            "referenced_documents": self.referenced_documents,
            "open_items": self.open_items,
            "blocking_issues": self.blocking_issues,
        }


@dataclass
class SessionOutputs:
    """Three-output generation results from the Writer agent."""
    tech_notes: str | None = None
    customer_summary: str | None = None
    escalation_brief: str | None = None

    def to_dict(self) -> dict:
        return {
            "tech_notes": self.tech_notes,
            "customer_summary": self.customer_summary,
            "escalation_brief": self.escalation_brief,
        }


@dataclass
class VehicleContext:
    """Structured vehicle info for a session."""
    year: int | None = None
    make: str = ""
    model: str = ""
    trim: str | None = None
    vin: str | None = None


@dataclass
class RepairOrder:
    """Repair order info for a session."""
    number: str | None = None
    mileage: int | None = None
    customer_concern: str = ""


@dataclass
class Session:
    """Full session state matching the locked schema — central state object for Firestore/JSON."""
    id: str = ""
    schema_version: str = "1.0"
    type: str = "session"
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    vehicle: VehicleContext = field(default_factory=VehicleContext)
    repair_order: RepairOrder = field(default_factory=RepairOrder)
    intake_context: IntakeContext = field(default_factory=IntakeContext)
    transcript: SessionTranscript = field(default_factory=SessionTranscript)
    synthesis: SessionSynthesis = field(default_factory=SessionSynthesis)
    outputs: SessionOutputs = field(default_factory=SessionOutputs)
    phase: SessionPhase = SessionPhase.IDLE
    ended_at: str | None = None

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "schema_version": self.schema_version,
            "type": self.type,
            "created_at": self.created_at,
            "vehicle": {
                "year": self.vehicle.year,
                "make": self.vehicle.make,
                "model": self.vehicle.model,
                "trim": self.vehicle.trim,
                "vin": self.vehicle.vin,
            },
            "repair_order": {
                "number": self.repair_order.number,
                "mileage": self.repair_order.mileage,
                "customer_concern": self.repair_order.customer_concern,
            },
            "intake_context": {
                "vehicle": self.intake_context.vehicle,
                "relevant_tsbs": self.intake_context.relevant_tsbs,
                "relevant_issues": self.intake_context.relevant_issues,
                "complaint_patterns": self.intake_context.complaint_patterns,
                "customer_concern_analysis": self.intake_context.customer_concern_analysis,
                "suggested_diagnostic_flow": self.intake_context.suggested_diagnostic_flow,
            },
            "transcript": {
                "entries": self.transcript.entries,
                "findings": self.transcript.findings,
            },
            "synthesis": self.synthesis.to_dict(),
            "outputs": self.outputs.to_dict(),
            "phase": self.phase.value,
            "ended_at": self.ended_at,
        }
