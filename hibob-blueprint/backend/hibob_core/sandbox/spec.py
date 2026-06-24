"""Sandbox execution spec (Phase 7, ADR 0011). Pure.

Network/filesystem exceptions are EXPLICIT allowlist entries derived from a tool's registry
definition (input_schema_json / constraints), never an ambient default. Default posture is the
most locked-down: no network, read-only filesystem, no workdir.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field

from hibob_core.config import settings


@dataclass
class SandboxSpec:
    container_image: str
    network_mode: str = "none"          # none | bridge (only via explicit allow_hosts)
    filesystem_mode: str = "read_only"  # read_only | rw (only for an explicit workdir_scope)
    workdir_scope: str | None = None
    allow_hosts: list[str] = field(default_factory=list)


def spec_for_tool(tool: dict) -> SandboxSpec:
    """Build a locked-down spec from a tool row. Exceptions come only from its constraints."""
    schema = tool.get("input_schema_json") or {}
    if isinstance(schema, str):
        try:
            schema = json.loads(schema)
        except json.JSONDecodeError:
            schema = {}
    constraints = schema.get("constraints", schema) if isinstance(schema, dict) else {}
    allow_hosts = list(constraints.get("allow_hosts", []))
    network_mode = "bridge" if allow_hosts else "none"
    workdir = constraints.get("workdir_scope")
    return SandboxSpec(
        container_image=settings.sandbox_image,
        network_mode=network_mode,
        filesystem_mode="rw" if workdir else "read_only",
        workdir_scope=workdir,
        allow_hosts=allow_hosts,
    )
