"""Runs a full session's trajectory through the engine, call by call.

This is the one place that wires simulation -> graph -> decision
together for a whole session at once; engine/decision.py itself only
ever sees a single call. Used by the benchmark runner, the baselines
(for interface parity), and the API layer.
"""
from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, field

from simulation.agent import MockProcurementAgent, ToolCallSpec

from .decision import evaluate_call
from .graph import SessionGraph
from .models import Decision, Trace
from .policy import Policy


@dataclass
class SessionEvalResult:
    session_id: str
    final_decision: Decision
    traces: list[Trace] = field(default_factory=list)  # sink calls only, in order

    @property
    def matched_conflict_class(self) -> str | None:
        for t in self.traces:
            if t.decision != Decision.ALLOW:
                return t.matched_conflict_class
        return None


def run_session(
    specs: Iterable[ToolCallSpec], session_id: str, policy: Policy
) -> SessionEvalResult:
    agent = MockProcurementAgent(session_id)
    graph = SessionGraph(session_id=session_id, policy=policy)

    traces: list[Trace] = []
    final = Decision.ALLOW
    for spec in specs:
        node = agent.build_node(spec)
        result = evaluate_call(graph, node)
        if result.trace is None:
            continue
        traces.append(result.trace)
        if result.decision == Decision.BLOCK:
            final = Decision.BLOCK
        elif result.decision == Decision.ESCALATE and final == Decision.ALLOW:
            final = Decision.ESCALATE

    return SessionEvalResult(session_id=session_id, final_decision=final, traces=traces)


def stream_session(specs: Iterable[ToolCallSpec], session_id: str, policy: Policy):
    """Same evaluation as run_session, but yields one event per call as it
    happens -- what the API's WebSocket layer streams to the frontend for
    the live-build graph effect."""
    agent = MockProcurementAgent(session_id)
    graph = SessionGraph(session_id=session_id, policy=policy)

    for spec in specs:
        node = agent.build_node(spec)
        result = evaluate_call(graph, node)
        yield {
            "call_id": node.call_id,
            "tool": node.tool,
            "resource_id": node.resource_id,
            "vendor_id": node.vendor_id,
            "period": node.period,
            "recipient": node.recipient,
            "is_sink": node.is_sink,
            "compartment_tags": dict(node.compartment_tags),
            "decision": result.decision.value,
            "trace": result.trace.to_dict() if result.trace else None,
        }
