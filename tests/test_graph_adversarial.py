"""Adversarial graph-logic probes, added by the pre-deployment audit
(2026-09-17): resource/vendor/period identity, session boundaries, ancestor
traversal, interleaving, duplicate/repeated access -- see also
tests/test_false_positives.py for the session-level (run_session) versions
of several of these."""
from engine.graph import SessionGraph
from engine.models import CallNode
from engine.policy import load_policy
from engine.decision import evaluate_call
from engine.session_runner import run_session
from simulation.agent import ToolCallSpec

POLICY = load_policy()


def _node(call_id, tool, vendor_id=None, period=None, payload_refs=None, recipient=None,
          resource_id=None, timestamp=None):
    return CallNode(
        call_id=call_id, tool=tool, session_id="adv", timestamp=timestamp or int(call_id[1:]),
        resource_id=resource_id or call_id, vendor_id=vendor_id, period=period,
        recipient=recipient, payload_refs=payload_refs or [],
    )


def test_repeated_access_to_same_resource_counts_once():
    graph = SessionGraph(session_id="adv1", policy=POLICY)
    for i in range(5):
        evaluate_call(graph, _node(f"d{i}", "read_invoice", vendor_id="V_Acme", period="Q1",
                                    resource_id="inv_x"))
    result = evaluate_call(
        graph,
        _node("d5", "send_notification", vendor_id="V_Acme",
              payload_refs=[f"d{i}" for i in range(5)], recipient="alex_categorymgr"),
    )
    match = next(m for m in result.trace.matches if m.conflict_class == "vendor_pricing_confidentiality")
    assert match.actual_count == 1


def test_ancestor_closure_never_includes_a_call_that_happens_after_the_sink():
    graph = SessionGraph(session_id="adv2", policy=POLICY)
    evaluate_call(graph, _node("b1", "read_invoice", vendor_id="V_Acme", period="Q1", timestamp=1))
    evaluate_call(
        graph,
        _node("b2", "send_notification", vendor_id="V_Acme", payload_refs=["b1"],
              recipient="alex_categorymgr", timestamp=2),
    )
    evaluate_call(graph, _node("b3", "read_invoice", vendor_id="V_Acme", period="Q2", timestamp=3))

    ancestors = graph.ancestor_closure(graph.nodes["b2"])
    assert "b3" not in {n.call_id for n in ancestors}


def test_session_isolation_under_resource_id_collision():
    """Two independent sessions that coincidentally reuse the same
    resource_id string must never contaminate each other."""
    session_a = [
        ToolCallSpec("read_invoice", resource_id="inv_1", vendor_id="V_Acme", period="Q1"),
        ToolCallSpec("read_invoice", resource_id="inv_2", vendor_id="V_Boreal", period="Q1"),
        ToolCallSpec("send_notification", resource_id="n1", vendor_id="V_Acme",
                     recipient="alex_categorymgr", payload_refs=["inv_1", "inv_2"]),
    ]
    session_b = [
        ToolCallSpec("read_invoice", resource_id="inv_1", vendor_id="V_Kepler", period="Q3"),
        ToolCallSpec("send_notification", resource_id="n1", vendor_id="V_Kepler",
                     recipient="alex_categorymgr", payload_refs=["inv_1"]),
    ]
    result_a = run_session(session_a, "session-A", POLICY)
    result_b = run_session(session_b, "session-B", POLICY)
    assert result_a.final_decision.value == "BLOCK"
    assert result_b.final_decision.value == "ALLOW"


def test_dangling_payload_ref_does_not_crash_or_phantom_count():
    calls = [
        ToolCallSpec("read_invoice", resource_id="inv_1", vendor_id="V_Acme", period="Q1"),
        ToolCallSpec("send_notification", resource_id="n1", vendor_id="V_Acme",
                     recipient="alex_categorymgr", payload_refs=["inv_1", "inv_DOES_NOT_EXIST"]),
    ]
    result = run_session(calls, "session-dangling-ref", POLICY)
    assert result.final_decision.value == "ALLOW"
    match = next(
        m for m in result.traces[-1].matches if m.conflict_class == "vendor_pricing_confidentiality"
    )
    assert match.actual_count == 1


def test_unrelated_resource_same_session_not_linked_without_shared_attribute():
    graph = SessionGraph(session_id="adv5", policy=POLICY)
    a = graph.add_call(_node("e1", "read_invoice", vendor_id="V_Acme", period="Q1"))
    b = graph.add_call(_node("e2", "read_invoice", vendor_id="V_Kepler", period="Q2"))
    assert graph._linked(a, b) is False
