"""The 6-tool mock invoice-processing agent / tool-call simulator.

This is deliberately NOT an LLM agent. It takes a declarative list of
`ToolCallSpec` (the trajectory a real agent would have produced -- see
/fixtures/) and turns it into a stream of `engine.models.CallNode`
objects with session-scoped call ids and timestamps, resolving
payload_refs (declared by resource_id) into call_ids as it goes. It
performs no authorization logic itself -- that's entirely engine/.
"""
from __future__ import annotations

from collections.abc import Iterable, Iterator
from dataclasses import dataclass, field
from typing import Any

from engine.models import CallNode

#: the fixed 6-tool surface of the simulated AP/procurement agent
TOOLS = (
    "read_invoice",
    "read_purchase_order",
    "search_vendor_db",
    "update_vendor_record",
    "create_draft_payment",
    "send_notification",
)


@dataclass
class ToolCallSpec:
    """One declared tool call in a trajectory, before it is turned into a
    graph node. `payload_refs` and cross-call resource references are
    expressed via `resource_id`, not `call_id`, since fixtures are written
    without knowledge of the call ids the agent will assign.
    """

    tool: str
    resource_id: str | None = None
    vendor_id: str | None = None
    period: str | None = None
    provenance: str | None = None
    recipient: str | None = None
    payload_refs: list[str] = field(default_factory=list)
    params: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.tool not in TOOLS:
            raise ValueError(f"Unknown tool {self.tool!r}; must be one of {TOOLS}")


class MockProcurementAgent:
    """Streams `ToolCallSpec`s into session-scoped `CallNode`s."""

    def __init__(self, session_id: str):
        self.session_id = session_id
        self._resource_to_call_id: dict[str, str] = {}
        self._counter = 0

    def build_node(self, spec: ToolCallSpec) -> CallNode:
        self._counter += 1
        call_id = f"{self.session_id}-c{self._counter}"
        resolved_refs = [
            self._resource_to_call_id[ref]
            for ref in spec.payload_refs
            if ref in self._resource_to_call_id
        ]
        node = CallNode(
            call_id=call_id,
            tool=spec.tool,
            session_id=self.session_id,
            timestamp=self._counter,
            resource_id=spec.resource_id,
            vendor_id=spec.vendor_id,
            period=spec.period,
            provenance=spec.provenance,
            recipient=spec.recipient,
            payload_refs=resolved_refs,
            params=dict(spec.params),
        )
        if spec.resource_id:
            self._resource_to_call_id[spec.resource_id] = call_id
        return node

    def stream(self, specs: Iterable[ToolCallSpec]) -> Iterator[CallNode]:
        for spec in specs:
            yield self.build_node(spec)
