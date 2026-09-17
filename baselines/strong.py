"""Baseline-Strong: a stateless, per-request, Cedar-style point rule.

This is a *separate*, simpler implementation from engine/ -- it does not
use the session graph or the ancestor-closure algorithm at all. For each
`send_notification` request it looks only at the vendors named in that
one request's payload_refs (a shallow, single-hop lookup of resources it
has already seen in this stream -- not a multi-hop graph traversal) and
applies exactly one hardcoded rule: cross-vendor pricing confidentiality.

It has no notion of quarters/periods whatsoever, so it structurally
cannot catch Attack 2 (which is single-vendor). This is not a bug to
"fix" -- a real security team plausibly ships exactly this rule after
Attack 1's pattern becomes known, and the honest gap it leaves is the
point of the baseline comparison (see repository README).
"""
from __future__ import annotations

from collections.abc import Iterable

from engine.models import Decision, Trace
from engine.policy import Policy
from engine.session_runner import SessionEvalResult
from simulation.agent import MockProcurementAgent, ToolCallSpec

NAME = "Baseline-Strong"

# Hand-configured, single-rule clearance table -- deliberately NOT
# sourced from policy/clearances.yaml's annual_spend_synthesis entries,
# because this baseline was never given that rule.
VENDOR_PRICING_THRESHOLD = {
    "alex_categorymgr": 1,
    "finance_director": 5,
}


def run_session(
    specs: Iterable[ToolCallSpec], session_id: str, policy: Policy | None = None
) -> SessionEvalResult:
    agent = MockProcurementAgent(session_id)
    resource_vendor: dict[str, str] = {}
    traces: list[Trace] = []

    for spec in specs:
        node = agent.build_node(spec)
        if node.resource_id and node.vendor_id:
            resource_vendor[node.resource_id] = node.vendor_id

        if node.tool != "send_notification":
            continue

        vendors_in_request = {
            resource_vendor[ref]
            for ref in spec.payload_refs
            if ref in resource_vendor
        }
        count = len(vendors_in_request)
        threshold = VENDOR_PRICING_THRESHOLD.get(node.recipient, 0)
        decision = Decision.BLOCK if count > threshold else Decision.ALLOW

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
