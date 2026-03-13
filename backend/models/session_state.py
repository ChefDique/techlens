"""Session state models for the TechLens three-state architecture."""

from enum import Enum
from dataclasses import dataclass, field


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
    entries: list = field(default_factory=list)  # [{role: str, text: str}]
    findings: list = field(default_factory=list)  # Logged findings from tools

    def add(self, role: str, text: str) -> None:
        self.entries.append({"role": role, "text": text})

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
