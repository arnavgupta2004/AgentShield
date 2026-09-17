"""Proves the §4c claim: adding a new conflict class requires ONLY a
policy-data edit, never an engine code change.

We run Attack 2 through the exact same `engine.session_runner.run_session`
function twice: once loaded with the vendor-only policy variant (which
has no annual_spend_synthesis entry), and once with the full policy.
Zero lines of engine/ differ between the two runs -- only the YAML
passed to `load_policy` changes.
"""
from pathlib import Path

from engine.policy import load_policy
from engine.session_runner import run_session
from fixtures.sessions import ATTACK1, ATTACK2

FULL_POLICY_DIR = Path(__file__).resolve().parent.parent / "policy"
VENDOR_ONLY_POLICY_DIR = FULL_POLICY_DIR / "variants" / "vendor_only"


def test_vendor_only_policy_misses_attack2_but_catches_attack1():
    policy = load_policy(VENDOR_ONLY_POLICY_DIR)

    for fixture in ATTACK2:
        result = run_session(fixture.calls, fixture.session_id, policy)
        assert result.final_decision.value == "ALLOW", (
            f"{fixture.session_id} should NOT be caught by the vendor-only "
            "policy -- this demonstrates the baseline's honest limitation, "
            "not a bug."
        )

    for fixture in ATTACK1:
        result = run_session(fixture.calls, fixture.session_id, policy)
        assert result.final_decision.value == "BLOCK", (
            f"{fixture.session_id} should still be caught -- the vendor "
            "rule it needs IS in this policy variant."
        )


def test_full_policy_catches_both_attacks_same_engine_function():
    policy = load_policy(FULL_POLICY_DIR)

    for fixture in ATTACK1 + ATTACK2:
        result = run_session(fixture.calls, fixture.session_id, policy)
        assert result.final_decision.value == "BLOCK", fixture.session_id

    for fixture in ATTACK2:
        result = run_session(fixture.calls, fixture.session_id, policy)
        assert result.matched_conflict_class == "annual_spend_synthesis"

    for fixture in ATTACK1:
        result = run_session(fixture.calls, fixture.session_id, policy)
        assert result.matched_conflict_class == "vendor_pricing_confidentiality"


def test_engine_source_never_names_a_conflict_class_or_vendor():
    """Static check backing the §4c claim: /engine/ contains zero
    references to specific conflict-class names, vendor names, or
    attack labels. Adding a class means editing YAML, not this code."""
    engine_dir = Path(__file__).resolve().parent.parent / "engine"
    forbidden = [
        "vendor_pricing_confidentiality",
        "annual_spend_synthesis",
        "V_Acme",
        "V_Boreal",
        "attack1",
        "attack2",
        "alex_categorymgr",
    ]
    for py_file in engine_dir.glob("*.py"):
        text = py_file.read_text(encoding="utf-8")
        for token in forbidden:
            assert token not in text, f"{py_file.name} references {token!r} -- move it to policy data"
