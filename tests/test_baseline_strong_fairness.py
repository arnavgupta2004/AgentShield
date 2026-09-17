"""Fairness guard for Baseline-Strong, added by the pre-deployment audit
(2026-09-17): asserts its hardcoded VENDOR_PRICING_THRESHOLD table stays
in sync with policy/clearances.yaml's real vendor_pricing_confidentiality
values. If someone edits the policy threshold later without updating the
baseline, this test catches the silent divergence that would make the
Baseline-Strong-vs-AgentShield comparison unfair (either too weak or too
strong a baseline) before it ships."""
from baselines.strong import VENDOR_PRICING_THRESHOLD
from engine.policy import load_policy

POLICY = load_policy()


def test_baseline_strong_thresholds_match_real_policy_exactly():
    for recipient, threshold in VENDOR_PRICING_THRESHOLD.items():
        real = POLICY.clearance_for(recipient, "vendor_pricing_confidentiality")
        assert threshold == real, (
            f"Baseline-Strong's hardcoded threshold for {recipient!r} ({threshold}) "
            f"no longer matches policy/clearances.yaml ({real}) -- the baseline "
            "comparison is no longer apples-to-apples."
        )
