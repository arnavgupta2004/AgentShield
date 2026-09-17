"""Policy loading.

This module reads policy DATA (YAML) and validates its shape. It contains
no knowledge of what any conflict class or tool is *called* -- adding a
new conflict class or recipient requires editing the YAML files in
/policy/, never this file.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

DEFAULT_POLICY_DIR = Path(__file__).resolve().parent.parent / "policy"


@dataclass
class ConflictClass:
    name: str
    description: str
    compartment_key: list[str]  # resource attribute names that define a compartment
    margin: int = 0  # ESCALATE band width above the clearance threshold


@dataclass
class ToolSpec:
    name: str
    sink: bool
    read_only: bool = False


@dataclass
class Policy:
    conflict_classes: dict[str, ConflictClass]
    # recipient -> conflict_class -> integer clearance threshold
    clearances: dict[str, dict[str, int]]
    tools: dict[str, ToolSpec]
    # the single resource attribute treated as "same underlying business
    # object" for coarse graph linkage (e.g. pulling a search_vendor_db
    # call into an invoice's ancestor closure even though it carries no
    # period). Policy DATA, not an engine constant -- see engine/graph.py.
    linkage_attribute: str | None = None
    source_files: list[str] = field(default_factory=list)

    def clearance_for(self, recipient: str, conflict_class: str) -> int:
        try:
            return self.clearances[recipient][conflict_class]
        except KeyError as exc:
            raise PolicyError(
                f"No clearance threshold declared for recipient={recipient!r} "
                f"conflict_class={conflict_class!r}. Every (recipient, conflict "
                f"class) pair must be explicit in policy/clearances.yaml."
            ) from exc

    def is_sink(self, tool: str) -> bool:
        spec = self.tools.get(tool)
        return bool(spec and spec.sink)


class PolicyError(Exception):
    pass


def _load_yaml(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as fh:
        data = yaml.safe_load(fh) or {}
    return data


def load_policy(policy_dir: str | Path | None = None) -> Policy:
    """Load the full policy bundle from a directory of YAML files.

    Expected files:
      - conflict_classes.yaml  (conflict class declarations, incl. margin)
      - clearances.yaml        (per-recipient thresholds per class)
      - tool_permissions.yaml  (which tools are sinks)
    """
    directory = Path(policy_dir) if policy_dir else DEFAULT_POLICY_DIR

    cc_path = directory / "conflict_classes.yaml"
    clear_path = directory / "clearances.yaml"
    tools_path = directory / "tool_permissions.yaml"

    cc_raw = _load_yaml(cc_path)
    clear_raw = _load_yaml(clear_path)
    tools_raw = _load_yaml(tools_path)

    conflict_classes: dict[str, ConflictClass] = {}
    for name, spec in (cc_raw.get("conflict_classes") or {}).items():
        conflict_classes[name] = ConflictClass(
            name=name,
            description=spec.get("description", ""),
            compartment_key=list(spec["compartment_key"]),
            margin=int(spec.get("margin", 0)),
        )

    clearances: dict[str, dict[str, int]] = {}
    for recipient, thresholds in (clear_raw.get("recipients") or {}).items():
        clearances[recipient] = {k: int(v) for k, v in thresholds.items()}

    tools: dict[str, ToolSpec] = {}
    for name, spec in (tools_raw.get("tools") or {}).items():
        tools[name] = ToolSpec(
            name=name,
            sink=bool(spec.get("sink", False)),
            read_only=bool(spec.get("read_only", False)),
        )

    policy = Policy(
        conflict_classes=conflict_classes,
        clearances=clearances,
        tools=tools,
        linkage_attribute=cc_raw.get("linkage_attribute"),
        source_files=[str(cc_path), str(clear_path), str(tools_path)],
    )
    _validate(policy)
    return policy


def _validate(policy: Policy) -> None:
    if not policy.conflict_classes:
        raise PolicyError("No conflict classes declared.")
    if not policy.tools:
        raise PolicyError("No tools declared.")
    for recipient, thresholds in policy.clearances.items():
        missing = set(policy.conflict_classes) - set(thresholds)
        if missing:
            raise PolicyError(
                f"Recipient {recipient!r} is missing clearance thresholds for "
                f"conflict classes: {sorted(missing)}"
            )
