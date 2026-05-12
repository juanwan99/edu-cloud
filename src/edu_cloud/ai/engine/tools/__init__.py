"""Pydantic AI native tools — migrated from legacy @registry.register pattern.

Provides collect_all_tools() and filter_tools_for_role() for EduAgentRuntime
to dynamically build the tool set per request.
"""
from __future__ import annotations

from typing import Any


def collect_all_tools() -> list[Any]:
    """Import all tool modules and return every @edu_tool decorated function."""
    from edu_cloud.ai.engine.tools import (
        actions,
        analytics,
        analytics_compare,
        analytics_report,
        analytics_score,
        artifact_query,
        bank,
        card_layout,
        conduct,
        exams,
        grading_ops,
        homework,
        knowledge,
        misc,
        profile,
        students,
    )

    all_tools: list[Any] = []
    for mod in [
        students, exams, analytics, analytics_score, analytics_compare,
        knowledge, profile, grading_ops, bank, homework, conduct,
        analytics_report, card_layout, misc, actions, artifact_query,
    ]:
        all_tools.extend(mod.ALL_TOOLS)
    return all_tools


def filter_tools_for_role(
    all_tools: list[Any],
    *,
    role: str,
    enabled_modules: frozenset[str],
    capabilities: dict[tuple[str, str], bool] | None = None,
) -> list[Any]:
    """Return only tools allowed for the given role and enabled modules.

    This is the registration-time RBAC filter. Tools still do a second
    hard check via PolicyToolGuardrail.before_tool() at call time.

    capabilities=None means skip capability check (before_tool still enforces).
    """
    allowed = []
    for fn in all_tools:
        meta = getattr(fn, "_edu_meta", None)
        if meta is None:
            continue
        if meta.allowed_roles and role not in meta.allowed_roles:
            continue
        if meta.module_code not in enabled_modules:
            continue
        if capabilities is not None and meta.requires_capabilities:
            if not all(capabilities.get(cap, False) for cap in meta.requires_capabilities):
                continue
        allowed.append(fn)
    return allowed
