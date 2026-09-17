"""Stronger genericity proof than test_policy_data_not_code.py: that test
only toggles which of the two SHIPPED classes are active. This test
constructs a THIRD conflict class with a structurally different pattern
-- keyed on `provenance` (data-trust level), not `vendor_id` or
`vendor_id`+`period` -- entirely in memory (no changes to policy/*.yaml
or engine/*.py), and proves the unmodified engine evaluates it correctly.

Not a production feature: this class exists only inside this test file.
Added by the pre-deployment audit (2026-09-17), per an explicit request to
prove genericity with a pattern that doesn't just reuse vendor_id.
"""
import hashlib
from pathlib import Path

from engine.policy import ConflictClass, Policy, ToolSpec
from engine.session_runner import run_session
from simulation.agent import ToolCallSpec

ENGINE_DIR = Path(__file__).resolve().parent.parent / "engine"


def _hash_engine_source() -> dict[str, str]:
    return {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in ENGINE_DIR.glob("*.py")}


def _policy_with_third_class() -> Policy:
    return Policy(
        conflict_classes={
            "vendor_pricing_confidentiality": ConflictClass(
                name="vendor_pricing_confidentiality", description="",
                compartment_key=["vendor_id"], margin=0,
            ),
            "provenance_trust_mixing": ConflictClass(
                name="provenance_trust_mixing",
                description="Distinct data-provenance levels synthesized into one sink call.",
                compartment_key=["provenance"],
                margin=0,
            ),
        },
        clearances={
            "alex_categorymgr": {
                "vendor_pricing_confidentiality": 1,
                "provenance_trust_mixing": 1,
            },
        },
        linkage_attribute="vendor_id",
        tools={
            "read_invoice": ToolSpec(name="read_invoice", sink=False),
            "update_vendor_record": ToolSpec(name="update_vendor_record", sink=False),
            "send_notification": ToolSpec(name="send_notification", sink=True),
        },
    )


def test_provenance_keyed_class_blocks_mixed_provenance_same_vendor():
    """Same vendor throughout (so the vendor_pricing class is NEVER
    triggered) -- only the provenance mix should cause the block, proving
    this is a genuinely distinct pattern, not vendor detection in disguise."""
    before = _hash_engine_source()
    policy = _policy_with_third_class()

    calls = [
        ToolCallSpec("read_invoice", resource_id="inv_trusted", vendor_id="V_Acme",
                     provenance="trusted"),
        ToolCallSpec("update_vendor_record", resource_id="upd_untrusted", vendor_id="V_Acme",
                     provenance="untrusted"),
        ToolCallSpec("send_notification", resource_id="n1", vendor_id="V_Acme",
                     recipient="alex_categorymgr", payload_refs=["inv_trusted", "upd_untrusted"]),
    ]
    result = run_session(calls, "third-class-attack", policy)

    assert result.final_decision.value == "BLOCK"
    assert result.matched_conflict_class == "provenance_trust_mixing"
    assert _hash_engine_source() == before, "engine/*.py must be byte-identical before and after"


def test_provenance_keyed_class_allows_single_provenance_same_vendor():
    policy = _policy_with_third_class()
    calls = [
        ToolCallSpec("read_invoice", resource_id="inv_trusted", vendor_id="V_Acme",
                     provenance="trusted"),
        ToolCallSpec("update_vendor_record", resource_id="upd_trusted2", vendor_id="V_Acme",
                     provenance="trusted"),
        ToolCallSpec("send_notification", resource_id="n1", vendor_id="V_Acme",
                     recipient="alex_categorymgr", payload_refs=["inv_trusted", "upd_trusted2"]),
    ]
    result = run_session(calls, "third-class-benign", policy)
    assert result.final_decision.value == "ALLOW"
