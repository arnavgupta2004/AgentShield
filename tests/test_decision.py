"""Unit tests for engine/decision.py in isolation: given a synthetic
graph + policy, assert correct ALLOW/BLOCK/ESCALATE."""
from engine.decision import evaluate_call
from engine.graph import SessionGraph
from engine.models import CallNode, Decision
from engine.policy import ConflictClass, Policy, ToolSpec


def _policy(margin: int = 0) -> Policy:
    return Policy(
        conflict_classes={
            "vendor_pricing_confidentiality": ConflictClass(
                name="vendor_pricing_confidentiality",
                description="",
                compartment_key=["vendor_id"],
                margin=margin,
            ),
        },
        clearances={
            "alex_categorymgr": {"vendor_pricing_confidentiality": 1},
            "finance_director": {"vendor_pricing_confidentiality": 5},
        },
        linkage_attribute="vendor_id",
        tools={
            "read_invoice": ToolSpec(name="read_invoice", sink=False),
            "send_notification": ToolSpec(name="send_notification", sink=True),
        },
    )


def _node(call_id, tool, vendor_id=None, payload_refs=None, recipient=None):
    return CallNode(
        call_id=call_id,
        tool=tool,
        session_id="s1",
        timestamp=int(call_id[1:]),
        resource_id=call_id,
        vendor_id=vendor_id,
        recipient=recipient,
        payload_refs=payload_refs or [],
    )


def test_non_sink_call_always_allows_and_has_no_trace():
    graph = SessionGraph(session_id="s1", policy=_policy())
    result = evaluate_call(graph, _node("c1", "read_invoice", vendor_id="V_Acme"))
    assert result.decision == Decision.ALLOW
    assert result.trace is None


def test_single_vendor_sink_under_threshold_allows():
    graph = SessionGraph(session_id="s1", policy=_policy())
    evaluate_call(graph, _node("c1", "read_invoice", vendor_id="V_Acme"))
    result = evaluate_call(
        graph, _node("c2", "send_notification", vendor_id="V_Acme", payload_refs=["c1"], recipient="alex_categorymgr")
    )
    assert result.decision == Decision.ALLOW
    assert result.trace.matched_conflict_class is None


def test_two_vendor_sink_over_threshold_blocks():
    graph = SessionGraph(session_id="s1", policy=_policy())
    evaluate_call(graph, _node("c1", "read_invoice", vendor_id="V_Acme"))
    evaluate_call(graph, _node("c2", "read_invoice", vendor_id="V_Boreal"))
    result = evaluate_call(
        graph,
        _node(
            "c3", "send_notification", vendor_id="V_Acme",
            payload_refs=["c1", "c2"], recipient="alex_categorymgr",
        ),
    )
    assert result.decision == Decision.BLOCK
    trace = result.trace
    assert trace.matched_conflict_class == "vendor_pricing_confidentiality"
    match = trace.matches[0]
    assert match.actual_count == 2
    assert match.clearance_threshold == 1
    assert sorted(match.member_compartments_involved) == [
        "vendor_pricing_confidentiality:V_Acme",
        "vendor_pricing_confidentiality:V_Boreal",
    ]


def test_same_pattern_allowed_for_higher_clearance_recipient():
    graph = SessionGraph(session_id="s1", policy=_policy())
    evaluate_call(graph, _node("c1", "read_invoice", vendor_id="V_Acme"))
    evaluate_call(graph, _node("c2", "read_invoice", vendor_id="V_Boreal"))
    result = evaluate_call(
        graph,
        _node(
            "c3", "send_notification", vendor_id="V_Acme",
            payload_refs=["c1", "c2"], recipient="finance_director",
        ),
    )
    assert result.decision == Decision.ALLOW


def test_margin_creates_an_escalate_band_before_block():
    graph = SessionGraph(session_id="s1", policy=_policy(margin=1))
    evaluate_call(graph, _node("c1", "read_invoice", vendor_id="V_Acme"))
    evaluate_call(graph, _node("c2", "read_invoice", vendor_id="V_Boreal"))
    result = evaluate_call(
        graph,
        _node(
            "c3", "send_notification", vendor_id="V_Acme",
            payload_refs=["c1", "c2"], recipient="alex_categorymgr",
        ),
    )
    # count=2, threshold=1, margin=1 -> within the escalate band, not a hard block
    assert result.decision == Decision.ESCALATE

    graph2 = SessionGraph(session_id="s2", policy=_policy(margin=1))
    evaluate_call(graph2, _node("d1", "read_invoice", vendor_id="V_Acme"))
    evaluate_call(graph2, _node("d2", "read_invoice", vendor_id="V_Boreal"))
    evaluate_call(graph2, _node("d3", "read_invoice", vendor_id="V_Solace"))
    result2 = evaluate_call(
        graph2,
        _node(
            "d4", "send_notification", vendor_id="V_Acme",
            payload_refs=["d1", "d2", "d3"], recipient="alex_categorymgr",
        ),
    )
    # count=3, threshold=1, margin=1 -> exceeds the escalate band -> BLOCK
    assert result2.decision == Decision.BLOCK
