"""Positive assertion about Baseline-Strong's honest limitation (spec §9):
a well-configured, real point-rule that genuinely misses Attack 2 because
it was never given a quarter/period-aware rule. This is not a bug to fix."""
from baselines import naive, strong
from engine.policy import load_policy
from fixtures.sessions import ATTACK1, ATTACK2

POLICY = load_policy()


def test_baseline_strong_catches_attack1():
    for fixture in ATTACK1:
        result = strong.run_session(fixture.calls, fixture.session_id, POLICY)
        assert result.final_decision.value == "BLOCK", fixture.session_id


def test_baseline_strong_misses_attack2():
    for fixture in ATTACK2:
        result = strong.run_session(fixture.calls, fixture.session_id, POLICY)
        assert result.final_decision.value == "ALLOW", (
            f"{fixture.session_id}: Baseline-Strong has no period-aware rule "
            "and should let this synthesis through -- that gap is the point."
        )


def test_baseline_naive_misses_both_attacks():
    for fixture in ATTACK1 + ATTACK2:
        result = naive.run_session(fixture.calls, fixture.session_id, POLICY)
        assert result.final_decision.value == "ALLOW", fixture.session_id
