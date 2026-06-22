"""Tests for PolicyToolGuardrail — three-layer hard boundary."""
from __future__ import annotations

from datetime import datetime

import pytest

from edu_cloud.ai.data_scope import DataScope
from edu_cloud.ai.engine.budget import AgentBudget
from edu_cloud.ai.engine.policy_guardrail import PolicyToolGuardrail, ToolDenied
from edu_cloud.ai.engine.tool_meta import EduToolMeta
from edu_cloud.ai.engine.trace_recorder import TraceRecorder


def _scope(
    role: str = "subject_teacher",
    can_write: bool = True,
    can_cross_school: bool = False,
    school_id: str = "s1",
) -> DataScope:
    return DataScope(
        user_id="u1", school_id=school_id, role=role,
        visible_class_ids=["c1"], visible_subject_codes=["math"],
        visible_grade_ids=None, visible_student_ids=None, district_ids=None,
        can_write=can_write, can_see_rankings=True,
        can_cross_school=can_cross_school,
        persona="teacher_assistant", version=1, computed_at=datetime.now(),
    )


def _meta(
    name: str = "test_tool",
    is_read_only: bool = True,
    allowed_roles: frozenset[str] = frozenset({"subject_teacher", "principal"}),
    module_code: str | None = "exam",
    requires_capabilities: frozenset[tuple[str, str]] = frozenset(),
    requires_modules: frozenset[str] = frozenset(),
) -> EduToolMeta:
    return EduToolMeta(
        name=name, module_code=module_code, domain="test",
        risk_level="low", is_read_only=is_read_only,
        allowed_roles=allowed_roles,
        requires_capabilities=requires_capabilities,
        requires_modules=requires_modules,
        sensitivity="school",
    )


def _guard(
    role: str = "subject_teacher",
    enabled_modules: frozenset[str] | None = None,
    capabilities: dict | None = None,
    scope: DataScope | None = None,
    budget: AgentBudget | None = None,
    metas: list[EduToolMeta] | None = None,
) -> PolicyToolGuardrail:
    s = scope or _scope(role=role)
    b = budget or AgentBudget()
    t = TraceRecorder("run1", "sess1", "s1", "u1", role)
    meta_list = metas or [_meta()]
    return PolicyToolGuardrail(
        role=role,
        enabled_modules=frozenset({"exam"}) if enabled_modules is None else enabled_modules,
        capabilities=capabilities or {},
        data_scope=s,
        budget=b,
        trace=t,
        tool_meta_registry={m.name: m for m in meta_list},
    )


# ── RBAC layer ──

@pytest.mark.asyncio
async def test_rbac_allows_matching_role():
    g = _guard(role="subject_teacher")
    record = await g.before_tool(_meta(), {})
    assert not record.denied


@pytest.mark.asyncio
async def test_rbac_denies_unauthorized_role():
    g = _guard(role="parent")
    with pytest.raises(ToolDenied, match="rbac") as exc_info:
        await g.before_tool(_meta(), {})
    assert exc_info.value.layer == "rbac"


@pytest.mark.asyncio
async def test_rbac_empty_allowed_roles_permits_all():
    m = _meta(allowed_roles=frozenset())
    g = _guard(role="anyone", metas=[m])
    record = await g.before_tool(m, {})
    assert not record.denied


# ── Module layer ──

@pytest.mark.asyncio
async def test_module_denies_disabled():
    g = _guard(enabled_modules=frozenset({"grading"}))
    with pytest.raises(ToolDenied, match="module"):
        await g.before_tool(_meta(module_code="exam"), {})


@pytest.mark.asyncio
async def test_module_allows_enabled():
    g = _guard(enabled_modules=frozenset({"exam"}))
    record = await g.before_tool(_meta(module_code="exam"), {})
    assert not record.denied


@pytest.mark.asyncio
async def test_module_allows_base_tool_without_school_switch():
    m = _meta(module_code=None)
    g = _guard(enabled_modules=frozenset(), metas=[m])
    record = await g.before_tool(m, {})
    assert not record.denied


@pytest.mark.asyncio
async def test_module_denies_missing_required_module():
    m = _meta(module_code="studio", requires_modules=frozenset({"exam"}))
    g = _guard(enabled_modules=frozenset({"studio"}), metas=[m])
    with pytest.raises(ToolDenied, match="module 'exam' not enabled"):
        await g.before_tool(m, {})


@pytest.mark.asyncio
async def test_module_allows_required_modules_enabled():
    m = _meta(module_code="studio", requires_modules=frozenset({"exam"}))
    g = _guard(enabled_modules=frozenset({"studio", "exam"}), metas=[m])
    record = await g.before_tool(m, {})
    assert not record.denied


# ── Capability layer ──

@pytest.mark.asyncio
async def test_capability_denies_missing():
    m = _meta(requires_capabilities=frozenset({("grading", "manage")}))
    g = _guard(capabilities={}, metas=[m])
    with pytest.raises(ToolDenied, match="capability"):
        await g.before_tool(m, {})


@pytest.mark.asyncio
async def test_capability_allows_granted():
    m = _meta(requires_capabilities=frozenset({("grading", "manage")}))
    g = _guard(capabilities={("grading", "manage"): True}, metas=[m])
    record = await g.before_tool(m, {})
    assert not record.denied


# ── Scope layer ──

@pytest.mark.asyncio
async def test_scope_denies_cross_school():
    g = _guard()
    with pytest.raises(ToolDenied, match="cross-school"):
        await g.before_tool(_meta(), {"school_id": "other_school"})


@pytest.mark.asyncio
async def test_scope_allows_same_school():
    g = _guard()
    record = await g.before_tool(_meta(), {"school_id": "s1"})
    assert not record.denied


@pytest.mark.asyncio
async def test_scope_allows_cross_school_for_admin():
    s = _scope(role="platform_admin", can_cross_school=True)
    m = _meta(allowed_roles=frozenset({"platform_admin"}))
    g = _guard(role="platform_admin", scope=s, metas=[m])
    record = await g.before_tool(m, {"school_id": "other"})
    assert not record.denied


@pytest.mark.asyncio
async def test_scope_denies_write_for_readonly_role():
    s = _scope(can_write=False)
    m = _meta(is_read_only=False)
    g = _guard(scope=s, metas=[m])
    with pytest.raises(ToolDenied, match="write denied"):
        await g.before_tool(m, {})


# ── Budget integration ──

@pytest.mark.asyncio
async def test_budget_exhaustion_denies():
    b = AgentBudget(max_tool_calls=0)
    g = _guard(budget=b)
    with pytest.raises(ToolDenied):
        await g.before_tool(_meta(), {})


# ── After-tool ──

@pytest.mark.asyncio
async def test_after_tool_debits_budget():
    b = AgentBudget()
    g = _guard(budget=b)
    m = _meta(is_read_only=False)
    record = await g.before_tool(m, {})
    await g.after_tool(record, "ok")
    assert b.used_tool_calls == 1
    assert b.used_write_ops == 1


@pytest.mark.asyncio
async def test_after_tool_records_trace():
    b = AgentBudget()
    t = TraceRecorder("run1", "sess1", "s1", "u1", "subject_teacher")
    g = PolicyToolGuardrail(
        role="subject_teacher", enabled_modules=frozenset({"exam"}),
        capabilities={}, data_scope=_scope(), budget=b, trace=t,
        tool_meta_registry={"test_tool": _meta()},
    )
    record = await g.before_tool(_meta(), {})
    await g.after_tool(record, {"data": [1, 2, 3]})
    assert len(t.events) == 1
    assert t.events[0].tool_name == "test_tool"


# ── Fingerprint ──

@pytest.mark.asyncio
async def test_args_fingerprint_deterministic():
    g = _guard()
    r1 = await g.before_tool(_meta(), {"a": 1, "b": 2})
    r2 = await g.before_tool(_meta(), {"b": 2, "a": 1})
    assert r1.args_fingerprint == r2.args_fingerprint
