"""Unit tests for engine/graph.py: linkage by vendor_id/period and
compartment tagging, in isolation from any fixture or policy variant."""
from engine.graph import SessionGraph
from engine.models import CallNode
from engine.policy import ConflictClass, Policy, ToolSpec


def _test_policy() -> Policy:
    return Policy(
        conflict_classes={
            "vendor_pricing_confidentiality": ConflictClass(
                name="vendor_pricing_confidentiality",
                description="",
                compartment_key=["vendor_id"],
                margin=0,
            ),
            "annual_spend_synthesis": ConflictClass(
                name="annual_spend_synthesis",
                description="",
                compartment_key=["vendor_id", "period"],
                margin=0,
            ),
        },
        clearances={
            "alex_categorymgr": {"vendor_pricing_confidentiality": 1, "annual_spend_synthesis": 2},
        },
        tools={
            "read_invoice": ToolSpec(name="read_invoice", sink=False),
            "search_vendor_db": ToolSpec(name="search_vendor_db", sink=False),
            "send_notification": ToolSpec(name="send_notification", sink=True),
        },
    )


def _node(call_id, tool, vendor_id=None, period=None, payload_refs=None, recipient=None):
    return CallNode(
        call_id=call_id,
        tool=tool,
        session_id="s1",
        timestamp=int(call_id[1:]),
        resource_id=call_id,
        vendor_id=vendor_id,
        period=period,
        recipient=recipient,
        payload_refs=payload_refs or [],
    )


def test_compartment_tagging_is_generic_and_policy_driven():
    policy = _test_policy()
    graph = SessionGraph(session_id="s1", policy=policy)

    n = graph.add_call(_node("c1", "read_invoice", vendor_id="V_Acme", period="Q1"))
    assert n.compartment_tags["vendor_pricing_confidentiality"] == "vendor_pricing_confidentiality:V_Acme"
    assert n.compartment_tags["annual_spend_synthesis"] == "annual_spend_synthesis:V_Acme:Q1"


def test_node_without_period_is_not_tagged_for_period_scoped_class():
    policy = _test_policy()
    graph = SessionGraph(session_id="s1", policy=policy)

    n = graph.add_call(_node("c1", "search_vendor_db", vendor_id="V_Acme"))
    assert "vendor_pricing_confidentiality" in n.compartment_tags
    assert "annual_spend_synthesis" not in n.compartment_tags


def test_linkage_by_shared_vendor_id():
    policy = _test_policy()
    graph = SessionGraph(session_id="s1", policy=policy)

    a = graph.add_call(_node("c1", "read_invoice", vendor_id="V_Acme", period="Q1"))
    b = graph.add_call(_node("c2", "search_vendor_db", vendor_id="V_Acme"))
    c = graph.add_call(_node("c3", "read_invoice", vendor_id="V_Boreal", period="Q1"))

    assert graph._linked(a, b) is True
    assert graph._linked(a, c) is False


def test_ancestor_closure_follows_payload_refs_then_vendor_linkage():
    policy = _test_policy()
    graph = SessionGraph(session_id="s1", policy=policy)

    graph.add_call(_node("c1", "read_invoice", vendor_id="V_Acme", period="Q1"))
    graph.add_call(_node("c2", "search_vendor_db", vendor_id="V_Acme"))
    graph.add_call(_node("c3", "read_invoice", vendor_id="V_Boreal", period="Q1"))  # unrelated noise
    sink = graph.add_call(
        _node("c4", "send_notification", vendor_id="V_Acme", payload_refs=["c1"], recipient="alex_categorymgr")
    )

    ancestors = graph.ancestor_closure(sink)
    ancestor_ids = {a.call_id for a in ancestors}

    assert ancestor_ids == {"c1", "c2"}  # c2 pulled in via vendor_id linkage; c3 excluded (different vendor)
