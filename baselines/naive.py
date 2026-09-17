"""Baseline-Naive.

Allows every individually-authorized call. No cross-call state, no
compartments, no clearance-vs-count comparison -- just the simplest
possible per-call allow-list check (is this a known tool, is the
recipient a known principal). This is what a system with *no*
aggregation-awareness looks like, and it's what both attacks sail
through: every call in Attack 1 and Attack 2 is individually
legitimate.
"""
from __future__ import annotations

from collections.abc import Iterable

from engine.models import Decision, Trace
from engine.policy import Policy
from engine.session_runner import SessionEvalResult
from simulation.agent import MockProcurementAgent, ToolCallSpec

NAME = "Baseline-Naive"


def run_session(
    specs: Iterable[ToolCallSpec], session_id: str, policy: Policy
) -> SessionEvalResult:
    agent = MockProcurementAgent(session_id)
    traces: list[Trace] = []

    for spec in specs:
        node = agent.build_node(spec)
        if not policy.is_sink(node.tool):
            continue

        allowed = node.tool in policy.tools and (
            node.recipient is None or node.recipient in policy.clearances
        )
        decision = Decision.ALLOW if allowed else Decision.BLOCK
        traces.append(
            Trace(
                call_id=node.call_id,
                session_id=session_id,
                tool=node.tool,
                recipient=node.recipient,
                decision=decision,
                matches=[],
                ancestor_call_ids=[],
            )
        )

    final = Decision.BLOCK if any(t.decision == Decision.BLOCK for t in traces) else Decision.ALLOW
    return SessionEvalResult(session_id=session_id, final_decision=final, traces=traces)
