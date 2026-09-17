"""Generic data model for the AgentShield engine.

Nothing in this module references a specific conflict class, vendor,
or attack scenario. Compartment tags are opaque strings computed by
``engine.graph`` from policy-declared attribute lists.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class Decision(str, Enum):
    ALLOW = "ALLOW"
    BLOCK = "BLOCK"
    ESCALATE = "ESCALATE"


@dataclass
class CallNode:
    """One tool-call node in a session graph."""

    call_id: str
    tool: str
    session_id: str
    timestamp: int
    resource_id: str | None = None
    vendor_id: str | None = None
    period: str | None = None
    provenance: str | None = None
    recipient: str | None = None
    payload_refs: list[str] = field(default_factory=list)
    params: dict[str, Any] = field(default_factory=dict)
    is_sink: bool = False

    # populated by SessionGraph after construction, generically from
    # policy-declared conflict classes' compartment_key attribute lists.
    compartment_tags: dict[str, str] = field(default_factory=dict)


@dataclass
class ConflictClassMatch:
    """Per-conflict-class tally for a single sink decision."""

    conflict_class: str
    member_compartments_involved: list[str]
    actual_count: int
    clearance_threshold: int
    margin: int
    verdict: Decision


@dataclass
class Trace:
    """Structured, auditable explanation for a sink decision."""

    call_id: str
    session_id: str
    tool: str
    recipient: str | None
    decision: Decision
    matches: list[ConflictClassMatch] = field(default_factory=list)
    ancestor_call_ids: list[str] = field(default_factory=list)

    @property
    def matched_conflict_class(self) -> str | None:
        """The class that drove the final decision, if any (BLOCK/ESCALATE)."""
        for m in self.matches:
            if m.verdict != Decision.ALLOW:
                return m.conflict_class
        return None

    def to_dict(self) -> dict[str, Any]:
        return {
            "call_id": self.call_id,
            "session_id": self.session_id,
            "tool": self.tool,
            "recipient": self.recipient,
            "decision": self.decision.value,
            "matched_conflict_class": self.matched_conflict_class,
            "ancestor_call_ids": self.ancestor_call_ids,
            "matches": [
                {
                    "conflict_class": m.conflict_class,
                    "member_compartments_involved": m.member_compartments_involved,
                    "actual_count": m.actual_count,
                    "clearance_threshold": m.clearance_threshold,
                    "margin": m.margin,
                    "verdict": m.verdict.value,
                }
                for m in self.matches
            ],
        }


@dataclass
class DecisionResult:
    """Return value of engine.decision.evaluate_call."""

    decision: Decision
    trace: Trace | None  # None for non-sink calls (no policy evaluation needed)
