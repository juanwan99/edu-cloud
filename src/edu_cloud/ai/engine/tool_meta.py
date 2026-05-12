"""EduToolMeta — frozen metadata for each registered tool."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Literal


@dataclass(frozen=True, slots=True)
class EduToolMeta:
    """Immutable descriptor attached to every @agent.tool at registration time.

    Drives PolicyToolGuardrail decisions: RBAC, module gating, budget class,
    sensitivity tier, and artifact policy.
    """

    name: str
    module_code: str
    domain: str
    risk_level: Literal["low", "medium", "high", "critical"]
    is_read_only: bool
    allowed_roles: frozenset[str]
    requires_capabilities: frozenset[tuple[str, str]]
    sensitivity: Literal["public", "school", "class", "student", "pii"]
    artifact_policy: Literal["inline", "auto", "always"] = "auto"
