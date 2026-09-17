"""Thin registry wiring system names to the engine/baseline functions.

The API layer is not allowed to contain authorization logic itself; this
module is the entire extent of its "policy awareness" -- which function
to call for which system name, and which policy variant to hand it.
"""
from __future__ import annotations

from pathlib import Path

from baselines import naive, strong
from engine import session_runner
from engine.policy import load_policy

_POLICY_DIR = Path(__file__).resolve().parent.parent / "policy"
_VENDOR_ONLY_DIR = _POLICY_DIR / "variants" / "vendor_only"

POLICY_VARIANTS = {
    "full": load_policy(_POLICY_DIR),
    "vendor_only": load_policy(_VENDOR_ONLY_DIR),
}

STREAM_FUNCS = {
    naive.NAME: naive.stream_session,
    strong.NAME: strong.stream_session,
    "AgentShield": session_runner.stream_session,
}

RUN_FUNCS = {
    naive.NAME: naive.run_session,
    strong.NAME: strong.run_session,
    "AgentShield": session_runner.run_session,
}


def system_names() -> list[str]:
    return list(STREAM_FUNCS.keys())


def policy_for(variant: str):
    if variant not in POLICY_VARIANTS:
        raise KeyError(f"unknown policy variant {variant!r}; choose one of {list(POLICY_VARIANTS)}")
    return POLICY_VARIANTS[variant]
