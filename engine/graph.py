"""Per-session resource-linkage graph.

Generic by construction: linkage is "nodes that share a resource
attribute" (vendor_id, and additionally period when a conflict class's
policy-declared compartment_key includes it) and compartment tags are
computed purely from the attribute names each conflict class declares
in policy. This file never mentions a specific conflict-class name,
vendor, or attack scenario -- see engine/decision.py for the sink
evaluation that consumes the tags this module computes.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from .models import CallNode
from .policy import Policy


def _compartment_tag(class_name: str, node: CallNode, compartment_key: list[str]) -> str | None:
    """Build a compartment tag for `node` under conflict class `class_name`.

    Returns None if the node doesn't carry all attributes the class's
    compartment_key requires (e.g. a node with no `period` can't be a
    member of a period-scoped class).
    """
    values: list[str] = []
    for attr in compartment_key:
        value = getattr(node, attr, None)
        if value is None:
            return None
        values.append(str(value))
    return class_name + ":" + ":".join(values)


@dataclass
class SessionGraph:
    """Builds and holds the call-node graph for a single session."""

    session_id: str
    policy: Policy
    nodes: dict[str, CallNode] = field(default_factory=dict)
    order: list[str] = field(default_factory=list)  # insertion order = temporal order

    def add_call(self, node: CallNode) -> CallNode:
        node.is_sink = self.policy.is_sink(node.tool)
        self._tag_compartments(node)
        self.nodes[node.call_id] = node
        self.order.append(node.call_id)
        return node

    def _tag_compartments(self, node: CallNode) -> None:
        for class_name, cc in self.policy.conflict_classes.items():
            tag = _compartment_tag(class_name, node, cc.compartment_key)
            if tag is not None:
                node.compartment_tags[class_name] = tag

    def _linked(self, a: CallNode, b: CallNode) -> bool:
        """Two nodes are graph-linked if they share a resource attribute
        that at least one declared conflict class uses to key compartments,
        OR if they share policy's single declared coarse linkage attribute
        (e.g. vendor_id) -- which pulls in supporting context nodes (like a
        search_vendor_db call) that a period-scoped class can't tag by
        itself, without those two nodes needing to also match on every
        other attribute a multi-attribute class's compartment_key lists.

        The coarse attribute is read from `policy.linkage_attribute`, not
        hardcoded here, so engine/ carries no fixed opinion about which
        resource attribute represents "the same underlying business
        object" across conflict classes -- that's a policy choice.
        Note it's a SINGLE named attribute, not "any attribute any class
        happens to key on": linking on every shared attribute (e.g. two
        different vendors' invoices that merely fall in the same period)
        would wrongly pull unrelated vendors' data into one ancestor
        closure -- see tests/test_false_positives.py.
        """
        if a.call_id == b.call_id:
            return False
        for cc in self.policy.conflict_classes.values():
            if all(getattr(a, attr, None) is not None for attr in cc.compartment_key):
                if all(
                    getattr(a, attr, None) == getattr(b, attr, None)
                    for attr in cc.compartment_key
                ):
                    return True
        attr = self.policy.linkage_attribute
        if attr:
            av, bv = getattr(a, attr, None), getattr(b, attr, None)
            if av is not None and av == bv:
                return True
        return False

    def ancestor_closure(self, sink: CallNode) -> list[CallNode]:
        """Graph-linked prior nodes reachable from the sink's referenced
        resources (payload_refs, or the sink's own resource attributes),
        restricted to nodes that occurred earlier in the session.
        """
        prior_ids = [cid for cid in self.order if cid != sink.call_id]
        prior_index = {cid: i for i, cid in enumerate(self.order)}
        sink_index = prior_index[sink.call_id]
        prior_nodes = [
            self.nodes[cid] for cid in prior_ids if prior_index[cid] < sink_index
        ]

        seeds: list[CallNode] = []
        for ref in sink.payload_refs:
            if ref in self.nodes:
                seeds.append(self.nodes[ref])
        if not seeds:
            # e.g. create_draft_payment references a resource directly via
            # vendor_id/resource_id rather than an explicit payload_refs list
            seeds = [
                n
                for n in prior_nodes
                if (sink.resource_id and n.resource_id == sink.resource_id)
                or (sink.vendor_id and n.vendor_id == sink.vendor_id)
            ]

        visited: dict[str, CallNode] = {s.call_id: s for s in seeds}
        frontier = list(seeds)
        while frontier:
            current = frontier.pop()
            for candidate in prior_nodes:
                if candidate.call_id in visited:
                    continue
                if self._linked(current, candidate):
                    visited[candidate.call_id] = candidate
                    frontier.append(candidate)

        return sorted(visited.values(), key=lambda n: prior_index[n.call_id])
