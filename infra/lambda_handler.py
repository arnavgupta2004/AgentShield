"""AWS Lambda adapter over the same engine used by api/main.py.

Contains no authorization logic -- it only parses an API Gateway proxy
event, calls engine.session_runner.run_session, and serializes the
result. This is the Lambda-side twin of
`api.main.evaluate_session` (POST /api/sessions/{id}/evaluate).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from engine.policy import load_policy  # noqa: E402
from engine.session_runner import run_session  # noqa: E402
from simulation.agent import ToolCallSpec  # noqa: E402

_POLICY_DIR = Path(__file__).resolve().parent.parent / "policy"
# Loaded once per warm Lambda execution environment, not per request.
# NOTE (see infra/DEPLOY.md "Known limitations"): this reads the same
# bundled YAML files as the local/API build, not the PolicyTable
# DynamoDB table declared in template.yaml -- see that file for why.
_POLICY = load_policy(_POLICY_DIR)


def _response(status: int, body: dict) -> dict:
    return {
        "statusCode": status,
        "headers": {"Content-Type": "application/json"},
        "body": json.dumps(body),
    }


def handler(event, _context):
    try:
        payload = json.loads(event.get("body") or "{}")
        session_id = payload["session_id"]
        calls = [ToolCallSpec(**c) for c in payload["calls"]]
    except (KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
        return _response(400, {"error": f"invalid request body: {exc}"})

    result = run_session(calls, session_id, _POLICY)
    return _response(
        200,
        {
            "session_id": session_id,
            "final_decision": result.final_decision.value,
            "matched_conflict_class": result.matched_conflict_class,
            "traces": [t.to_dict() for t in result.traces],
        },
    )
