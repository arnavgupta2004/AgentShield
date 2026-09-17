"""Production smoke test for a deployed AgentShield AWS Lambda.

Hits POST /sessions/{sessionId}/evaluate on a live deployment with real
fixtures from fixtures/sessions.py (never invented payloads) and checks
the response against both (a) the fixture's own expected_label /
expected_conflict_class and (b) the local engine's own live output for
the identical input -- so this catches both "AWS disagrees with the
benchmark" and "AWS disagrees with what's running locally right now"
regressions (e.g. AWS running a stale build after a local fix).

No AWS credentials are used or required -- this only calls the public
HTTPS API Gateway endpoint, the same way any client would.

Usage:
    python infra/smoke_test.py --url https://xxxx.execute-api.<region>.amazonaws.com/prod
    python infra/smoke_test.py --url ... --all          # all 30 fixtures
    AGENTSHIELD_AWS_URL=https://... python infra/smoke_test.py

Exit code is non-zero if any check fails, so this is safe to wire into a
CI job or a periodic health check later.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from engine.policy import load_policy  # noqa: E402
from engine.session_runner import run_session  # noqa: E402
from fixtures.sessions import ALL_SESSIONS  # noqa: E402

# One fixture per category by default -- fast, still covers every conflict
# class and every ALLOW-path category. --all runs the full 30.
DEFAULT_SESSION_IDS = [
    "benign-standard-00",
    "benign-two-quarter-00",
    "benign-high-clearance-00",
    "benign-bank-update-00",
    "attack1-two-vendor-sequential-00",
    "attack2-three-quarter-sequential-00",
]


def _calls_payload(fixture) -> list[dict]:
    return [
        {
            "tool": c.tool, "resource_id": c.resource_id, "vendor_id": c.vendor_id,
            "period": c.period, "provenance": c.provenance, "recipient": c.recipient,
            "payload_refs": c.payload_refs, "params": c.params,
        }
        for c in fixture.calls
    ]


def _call_aws(base_url: str, fixture, timeout: float) -> dict:
    body = json.dumps({
        "session_id": fixture.session_id,
        "calls": _calls_payload(fixture),
    }).encode()
    req = urllib.request.Request(
        f"{base_url.rstrip('/')}/sessions/{fixture.session_id}/evaluate",
        data=body, headers={"Content-Type": "application/json"}, method="POST",
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read())


def run_smoke_test(base_url: str, session_ids: list[str], timeout: float = 15.0) -> bool:
    policy = load_policy()
    by_id = {f.session_id: f for f in ALL_SESSIONS}

    all_ok = True
    print(f"AgentShield AWS smoke test against {base_url}")
    print(f"{'session_id':<42} {'expected':<8} {'local':<8} {'aws':<8} {'result'}")
    for sid in session_ids:
        fixture = by_id[sid]
        local_result = run_session(fixture.calls, fixture.session_id, policy)
        local_decision = local_result.final_decision.value
        local_class = local_result.matched_conflict_class

        try:
            aws_payload = _call_aws(base_url, fixture, timeout)
        except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError) as exc:
            print(f"{sid:<42} {fixture.expected_label:<8} {local_decision:<8} {'ERROR':<8} {exc}")
            all_ok = False
            continue

        aws_decision = aws_payload.get("final_decision")
        aws_class = aws_payload.get("matched_conflict_class")

        matches_fixture = aws_decision == fixture.expected_label
        matches_local = aws_decision == local_decision and aws_class == local_class
        ok = matches_fixture and matches_local
        all_ok &= ok

        result = "PASS" if ok else "*** FAIL ***"
        print(f"{sid:<42} {fixture.expected_label:<8} {local_decision:<8} {aws_decision:<8} {result}")
        if not ok:
            print(f"    fixture.expected_conflict_class={fixture.expected_conflict_class!r}"
                  f"  local matched={local_class!r}  aws matched={aws_class!r}")

    print()
    print("ALL CHECKS PASSED" if all_ok else "*** SMOKE TEST FAILED -- see FAIL rows above ***")
    return all_ok


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--url", default=os.environ.get("AGENTSHIELD_AWS_URL"),
        help="Base URL of the deployed API, e.g. "
             "https://xxxx.execute-api.<region>.amazonaws.com/prod "
             "(or set AGENTSHIELD_AWS_URL)",
    )
    parser.add_argument("--all", action="store_true", help="run all 30 fixtures, not just 6")
    parser.add_argument("--timeout", type=float, default=15.0)
    args = parser.parse_args()

    if not args.url:
        parser.error("--url is required (or set AGENTSHIELD_AWS_URL)")

    session_ids = [f.session_id for f in ALL_SESSIONS] if args.all else DEFAULT_SESSION_IDS
    ok = run_smoke_test(args.url, session_ids, args.timeout)
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
