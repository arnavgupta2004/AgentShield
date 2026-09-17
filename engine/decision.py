"""The core decision algorithm.

One function, `evaluate_call`, handles every sink call regardless of
which conflict class is involved. It never branches on a conflict-class
name, a vendor id, or an attack label -- it only ever asks "how many
distinct declared-policy compartment members of class C reach this sink,
and is that more than the recipient's clearance for C (plus its
configured margin)?". Everything scenario-specific lives in policy data
(engine/policy.py + /policy/*.yaml).
"""
from __future__ import annotations

from .graph import SessionGraph
from .models import CallNode, ConflictClassMatch, Decision, DecisionResult, Trace


def evaluate_call(graph: SessionGraph, node: CallNode) -> DecisionResult:
    graph.add_call(node)

    if not node.is_sink:
        return DecisionResult(decision=Decision.ALLOW, trace=None)

    ancestors = graph.ancestor_closure(node)
    involved = ancestors + [node]

    matches: list[ConflictClassMatch] = []
    final = Decision.ALLOW

    for class_name, cc in graph.policy.conflict_classes.items():
        tags = sorted(
            {n.compartment_tags[class_name] for n in involved if class_name in n.compartment_tags}
        )
        count = len(tags)
        if count == 0:
            continue

        threshold = graph.policy.clearance_for(node.recipient, class_name) if node.recipient else 0
        margin = cc.margin

        if count > threshold + margin:
            verdict = Decision.BLOCK
        elif count > threshold:
            verdict = Decision.ESCALATE
        else:
            verdict = Decision.ALLOW

        matches.append(
            ConflictClassMatch(
                conflict_class=class_name,
                member_compartments_involved=tags,
                actual_count=count,
                clearance_threshold=threshold,
                margin=margin,
                verdict=verdict,
            )
        )

        if verdict == Decision.BLOCK:
            final = Decision.BLOCK
        elif verdict == Decision.ESCALATE and final == Decision.ALLOW:
            final = Decision.ESCALATE

    trace = Trace(
        call_id=node.call_id,
        session_id=node.session_id,
        tool=node.tool,
        recipient=node.recipient,
        decision=final,
        matches=matches,
        ancestor_call_ids=[a.call_id for a in ancestors],
    )
    return DecisionResult(decision=final, trace=trace)
