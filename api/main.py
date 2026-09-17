"""FastAPI backend: submit/replay sessions, stream live decisions over
WebSocket, select which system evaluates a session, and fetch benchmark
results.

Contains NO authorization logic of its own -- every decision returned
here comes from engine/, baselines/, or benchmark/. See spec build
priority item 4.
"""
from __future__ import annotations

import asyncio

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

from benchmark.runner import run_benchmark
from fixtures.sessions import ALL_SESSIONS
from simulation.agent import ToolCallSpec

from .models import SessionSubmission
from .systems import POLICY_VARIANTS, RUN_FUNCS, STREAM_FUNCS, policy_for, system_names

app = FastAPI(title="AgentShield API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

_FIXTURES_BY_ID = {f.session_id: f for f in ALL_SESSIONS}
_custom_sessions: dict[str, list[ToolCallSpec]] = {}
_last_benchmark_results: dict | None = None


def _lookup_calls(session_id: str) -> list[ToolCallSpec] | None:
    fixture = _FIXTURES_BY_ID.get(session_id)
    if fixture is not None:
        return fixture.calls
    return _custom_sessions.get(session_id)


@app.get("/api/health")
def health():
    return {"status": "ok"}


@app.get("/api/systems")
def systems():
    return {"systems": system_names()}


@app.get("/api/policy-variants")
def policy_variants():
    return {"variants": list(POLICY_VARIANTS)}


@app.get("/api/fixtures")
def list_fixtures():
    return [
        {
            "session_id": f.session_id,
            "category": f.category,
            "expected_label": f.expected_label,
            "expected_conflict_class": f.expected_conflict_class,
            "num_calls": len(f.calls),
        }
        for f in ALL_SESSIONS
    ]


@app.get("/api/fixtures/{session_id}")
def get_fixture(session_id: str):
    fixture = _FIXTURES_BY_ID.get(session_id)
    if fixture is None:
        raise HTTPException(404, f"unknown session_id {session_id!r}")
    return {
        "session_id": fixture.session_id,
        "category": fixture.category,
        "expected_label": fixture.expected_label,
        "expected_conflict_class": fixture.expected_conflict_class,
        "calls": [
            {
                "tool": c.tool,
                "resource_id": c.resource_id,
                "vendor_id": c.vendor_id,
                "period": c.period,
                "provenance": c.provenance,
                "recipient": c.recipient,
                "payload_refs": c.payload_refs,
                "params": c.params,
            }
            for c in fixture.calls
        ],
    }


@app.post("/api/sessions")
def submit_session(submission: SessionSubmission):
    """Register a custom trajectory for later replay via the WebSocket
    endpoint, e.g. for demo scripting beyond the canned fixture set."""
    try:
        calls = [ToolCallSpec(**c.model_dump()) for c in submission.calls]
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    _custom_sessions[submission.session_id] = calls
    return {"session_id": submission.session_id, "num_calls": len(calls)}


@app.post("/api/sessions/{session_id}/evaluate")
def evaluate_session(session_id: str, system: str = "AgentShield", policy_variant: str = "full"):
    calls = _lookup_calls(session_id)
    if calls is None:
        raise HTTPException(404, f"unknown session_id {session_id!r}")
    run_fn = RUN_FUNCS.get(system)
    if run_fn is None:
        raise HTTPException(400, f"unknown system {system!r}; choose one of {system_names()}")
    try:
        policy = policy_for(policy_variant)
    except KeyError as exc:
        raise HTTPException(400, str(exc)) from exc
    result = run_fn(calls, session_id, policy)
    return {
        "session_id": session_id,
        "system": system,
        "policy_variant": policy_variant,
        "final_decision": result.final_decision.value,
        "matched_conflict_class": result.matched_conflict_class,
        "traces": [t.to_dict() for t in result.traces],
    }


@app.post("/api/benchmark/run")
def run_benchmark_endpoint():
    # Always the full policy -- that's the honest, deployed configuration.
    # The vendor_only variant is for the live "same engine, before/after
    # a policy edit" demo step via /api/sessions/{id}/evaluate instead.
    global _last_benchmark_results
    _last_benchmark_results = run_benchmark()
    return _last_benchmark_results


@app.get("/api/benchmark/results")
def get_benchmark_results():
    global _last_benchmark_results
    if _last_benchmark_results is None:
        _last_benchmark_results = run_benchmark()
    return _last_benchmark_results


@app.websocket("/ws/session/{session_id}")
async def stream_session_ws(
    websocket: WebSocket,
    session_id: str,
    system: str = "AgentShield",
    policy_variant: str = "full",
    delay_ms: int = 250,
):
    await websocket.accept()
    delay_ms = max(0, min(delay_ms, 5000))  # bound a client-supplied delay

    calls = _lookup_calls(session_id)
    if calls is None:
        await websocket.send_json({"type": "error", "message": f"unknown session_id {session_id!r}"})
        await websocket.close()
        return

    stream_fn = STREAM_FUNCS.get(system)
    if stream_fn is None:
        await websocket.send_json({
            "type": "error",
            "message": f"unknown system {system!r}; choose one of {system_names()}",
        })
        await websocket.close()
        return

    try:
        policy = policy_for(policy_variant)
    except KeyError as exc:
        await websocket.send_json({"type": "error", "message": str(exc)})
        await websocket.close()
        return

    fixture = _FIXTURES_BY_ID.get(session_id)
    await websocket.send_json({
        "type": "session_start",
        "session_id": session_id,
        "system": system,
        "policy_variant": policy_variant,
        "expected_label": fixture.expected_label if fixture else None,
        "expected_conflict_class": fixture.expected_conflict_class if fixture else None,
    })

    final_decision = "ALLOW"
    try:
        for event in stream_fn(calls, session_id, policy):
            if event["decision"] == "BLOCK":
                final_decision = "BLOCK"
            elif event["decision"] == "ESCALATE" and final_decision == "ALLOW":
                final_decision = "ESCALATE"
            await websocket.send_json({"type": "call", **event})
            if delay_ms > 0:
                await asyncio.sleep(delay_ms / 1000)

        await websocket.send_json({
            "type": "session_complete",
            "session_id": session_id,
            "system": system,
            "final_decision": final_decision,
        })
    except WebSocketDisconnect:
        return

    await websocket.close()
