"""Integration test: the full 30-session benchmark, run against all
three systems, asserting expected labels end to end."""
from benchmark.runner import run_benchmark


def test_thirty_session_benchmark_end_to_end():
    results = run_benchmark()
    assert results["total_sessions"] == 30

    agentshield_rows = [r for r in results["rows"] if r["system"] == "AgentShield"]
    assert len(agentshield_rows) == 30
    failures = [r["session_id"] for r in agentshield_rows if not r["passed"]]
    assert failures == [], f"AgentShield mislabeled: {failures}"

    m = results["metrics"]["AgentShield"]
    assert m["tp"] == 12  # 6 attack1 + 6 attack2
    assert m["fn"] == 0
    assert m["fp"] == 0
    assert m["tn"] == 18  # 10 + 3 + 3 + 2 benign/near-miss

    assert results["false_positive_rate_benign_subset"]["AgentShield"] == 0.0
    assert results["attack_breakdown"]["AgentShield::attack1"] == "6/6"
    assert results["attack_breakdown"]["AgentShield::attack2"] == "6/6"

    # Baseline-Strong: real, honest gap on Attack 2
    assert results["attack_breakdown"]["Baseline-Strong::attack1"] == "6/6"
    assert results["attack_breakdown"]["Baseline-Strong::attack2"] == "0/6"

    # Baseline-Naive: catches nothing
    assert results["attack_breakdown"]["Baseline-Naive::attack1"] == "0/6"
    assert results["attack_breakdown"]["Baseline-Naive::attack2"] == "0/6"
