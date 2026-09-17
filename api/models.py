"""Request/response models for the API layer only -- not used by engine/."""
from __future__ import annotations

from pydantic import BaseModel


class ToolCallIn(BaseModel):
    tool: str
    resource_id: str | None = None
    vendor_id: str | None = None
    period: str | None = None
    provenance: str | None = None
    recipient: str | None = None
    payload_refs: list[str] = []
    params: dict = {}


class SessionSubmission(BaseModel):
    session_id: str
    calls: list[ToolCallIn]
