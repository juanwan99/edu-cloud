"""Capability 行为测试。

历史：原文件名 fail_closed + 原断言要求 "no record = DENY"，与系统 INV-002
（tool_access.py:37、capability_service.py:156、test_tool_access_v2.py:69
均明确为 "无记录默认允许" fail-open）冲突。经审计 INV-002 是系统一致决策
（被 GPT 审查确认，见 docs/plans/2026-04-03-edu-agent-integration-review.md:47），
保留 fail-open 语义，此文件改为 fail-open 行为验证。

如未来改为 fail-closed，需同步改 tool_access.py / capability_service.py /
test_tool_access_v2.py 及前端角色能力配置逻辑。
"""
import pytest
from unittest.mock import AsyncMock
from edu_cloud.ai.tool_access import ToolAccessResolver
from edu_cloud.ai.registry import ToolSpec


def _make_spec(name, allowed_roles=None, module_code=None, requires_capabilities=None):
    return ToolSpec(
        name=name, description="test", parameters={},
        func=AsyncMock(), category="general",
        module_code=module_code, domain="general",
        allowed_roles=allowed_roles,
        requires_capabilities=requires_capabilities or [],
    )


def test_no_capability_record_allows():
    """INV-002：无 capability 记录 → ALLOW（fail-open，系统默认策略）。"""
    spec = _make_spec("tool_x", allowed_roles=["subject_teacher"],
                       requires_capabilities=[("analytics", "read")])
    resolver = ToolAccessResolver()
    result = resolver.resolve([spec], role="subject_teacher",
                               enabled_modules=set(),
                               capabilities={})
    assert len(result) == 1  # fail-open: no record = allow (INV-002)


def test_module_disabled_rejects():
    spec = _make_spec("tool_y", allowed_roles=["subject_teacher"],
                       module_code="grading")
    result = ToolAccessResolver().resolve([spec], role="subject_teacher",
                                          enabled_modules={"analytics"},
                                          capabilities={})
    assert len(result) == 0


def test_explicit_allow_passes():
    spec = _make_spec("tool_z", allowed_roles=["subject_teacher"],
                       requires_capabilities=[("analytics", "read")])
    result = ToolAccessResolver().resolve([spec], role="subject_teacher",
                                          enabled_modules=set(),
                                          capabilities={("analytics", "read"): True})
    assert len(result) == 1


def test_no_capability_requirement_passes():
    """Tool with empty requires_capabilities -> always passes capability check."""
    spec = _make_spec("tool_w", allowed_roles=["subject_teacher"],
                       requires_capabilities=[])
    result = ToolAccessResolver().resolve([spec], role="subject_teacher",
                                          enabled_modules=set(),
                                          capabilities={})
    assert len(result) == 1


def test_explicit_false_still_rejects():
    """Explicit False -> DENY (unchanged behavior)."""
    spec = _make_spec("tool_a", allowed_roles=["subject_teacher"],
                       requires_capabilities=[("exam", "write")])
    result = ToolAccessResolver().resolve([spec], role="subject_teacher",
                                          enabled_modules=set(),
                                          capabilities={("exam", "write"): False})
    assert len(result) == 0


def test_partial_capability_match_allows():
    """INV-002：部分显式 True + 其余无记录 → ALLOW。"""
    spec = _make_spec("tool_b", allowed_roles=["subject_teacher"],
                       requires_capabilities=[("exam", "read"), ("grading", "write")])
    result = ToolAccessResolver().resolve([spec], role="subject_teacher",
                                          enabled_modules=set(),
                                          capabilities={("exam", "read"): True})
    # grading.write 无记录 → fail-open → allow (INV-002)
    assert len(result) == 1


def test_all_capabilities_explicit_true_passes():
    """All required capabilities explicitly True -> ALLOW."""
    spec = _make_spec("tool_c", allowed_roles=["subject_teacher"],
                       requires_capabilities=[("exam", "read"), ("grading", "write")])
    result = ToolAccessResolver().resolve([spec], role="subject_teacher",
                                          enabled_modules=set(),
                                          capabilities={("exam", "read"): True,
                                                        ("grading", "write"): True})
    assert len(result) == 1
