"""Runs the 30-session fixture set against all three systems and
produces real comparison numbers. Nothing in this file is fabricated --
`run_benchmark()` actually executes every fixture against every system.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass

from baselines import naive as naive_system
from baselines import strong as strong_system
from engine.policy import load_policy
from engine.session_runner import run_session as agentshield_run_session
from fixtures.sessions import ALL_SESSIONS

from .metrics import compute_metrics

SYSTEMS = {
    naive_system.NAME: naive_system.run_session,
    strong_system.NAME: strong_system.run_session,
    "AgentShield": agentshield_run_session,
}


@dataclass
class SessionRunRow:
    session_id: str
    category: str
    expected_label: str
    expected_conflict_class: str | None
    system: str
    actual_decision: str
    matched_conflict_class: str | None
    passed: bool


def run_benchmark(policy_dir: str | None = None) -> dict:
    policy = load_policy(policy_dir)
    rows: list[SessionRunRow] = []

    for fixture in ALL_SESSIONS:
        for system_name, run_fn in SYSTEMS.items():
            result = run_fn(fixture.calls, fixture.session_id, policy)
            actual = result.final_decision.value
            expected_block = fixture.expected_label == "BLOCK"
            actual_block = actual != "ALLOW"
            passed = expected_block == actual_block
            rows.append(
                SessionRunRow(
                    session_id=fixture.session_id,
                    category=fixture.category,
                    expected_label=fixture.expected_label,
                    expected_conflict_class=fixture.expected_conflict_class,
                    system=system_name,
                    actual_decision=actual,
                    matched_conflict_class=result.matched_conflict_class,
                    passed=passed,
                )
            )

    metrics_by_system: dict[str, dict] = {}
    fpr_by_system: dict[str, float] = {}
    for system_name in SYSTEMS:
        system_rows = [r for r in rows if r.system == system_name]
        metrics_by_system[system_name] = compute_metrics(system_rows).to_dict()

        benign_rows = [r for r in system_rows if r.expected_label == "ALLOW"]
        fp = sum(1 for r in benign_rows if r.actual_decision != "ALLOW")
        fpr_by_system[system_name] = round(fp / len(benign_rows), 4) if benign_rows else 0.0

    attack_breakdown: dict[str, str] = {}
    for system_name in SYSTEMS:
        for category in ("attack1", "attack2"):
            cat_rows = [r for r in rows if r.system == system_name and r.category == category]
            caught = sum(1 for r in cat_rows if r.passed)
            attack_breakdown[f"{system_name}::{category}"] = f"{caught}/{len(cat_rows)}"

    return {
        "total_sessions": len(ALL_SESSIONS),
        "rows": [asdict(r) for r in rows],
        "metrics": metrics_by_system,
        "false_positive_rate_benign_subset": fpr_by_system,
        "attack_breakdown": attack_breakdown,
    }


if __name__ == "__main__":
    import json
    import sys

    results = run_benchmark()
    print(json.dumps(results, indent=2))

    print("\n=== Metrics ===", file=sys.stderr)
    for system, m in results["metrics"].items():
        print(f"{system}: {m}", file=sys.stderr)
    print("\n=== FPR (benign+near-miss subset) ===", file=sys.stderr)
    for system, fpr in results["false_positive_rate_benign_subset"].items():
        print(f"{system}: {fpr}", file=sys.stderr)
    print("\n=== Attack breakdown ===", file=sys.stderr)
    for k, v in results["attack_breakdown"].items():
        print(f"{k}: {v}", file=sys.stderr)
