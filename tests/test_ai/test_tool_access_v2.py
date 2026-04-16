import pytest
from edu_cloud.ai.registry import ToolSpec
from edu_cloud.ai.tool_access import ToolAccessResolver
from edu_cloud.ai.tool_context import ToolContext, ToolResult


def _make_spec(name, allowed_roles=None, module_code=None, requires_capabilities=None, sensitivity="school"):
    async def _noop(input: dict, ctx: ToolContext) -> ToolResult:
        return ToolResult(success=True, data=None)
    return ToolSpec(
        name=name, description=name, parameters={}, func=_noop,
        allowed_roles=allowed_roles, module_code=module_code,
        requires_capabilities=requires_capabilities or [],
        sensitivity=sensitivity, is_read_only=True,
    )


def test_rbac_filter():
    resolver = ToolAccessResolver()
    specs = [
        _make_spec("t1", allowed_roles=["admin"]),
        _make_spec("t2", allowed_roles=["teacher"]),
        _make_spec("t3", allowed_roles=None),  # open to all
    ]
    result = resolver.resolve(specs, role="teacher", enabled_modules=None, capabilities={})
    names = [s.name for s in result]
    assert "t1" not in names
    assert "t2" in names
    assert "t3" in names


def test_module_filter():
    resolver = ToolAccessResolver()
    specs = [
        _make_spec("t1", module_code="exam"),
        _make_spec("t2", module_code="grading"),
        _make_spec("t3"),  # no module
    ]
    result = resolver.resolve(specs, role="admin", enabled_modules={"exam"}, capabilities={})
    names = [s.name for s in result]
    assert "t1" in names
    assert "t2" not in names
    assert "t3" in names


def test_capability_filter():
    resolver = ToolAccessResolver()
    specs = [
        _make_spec("t1", requires_capabilities=[("analytics", "read")]),
        _make_spec("t2", requires_capabilities=[]),
    ]
    caps = {("analytics", "read"): True, ("analytics", "write"): False}
    result = resolver.resolve(specs, role="admin", enabled_modules=None, capabilities=caps)
    names = [s.name for s in result]
    assert "t1" in names
    assert "t2" in names


def test_capability_denied():
    resolver = ToolAccessResolver()
    specs = [
        _make_spec("t1", requires_capabilities=[("grading", "write")]),
    ]
    caps = {("grading", "write"): False}
    result = resolver.resolve(specs, role="admin", enabled_modules=None, capabilities=caps)
    assert len(result) == 0


def test_capability_default_allow():
    """未配置的 capability 默认允许（INV-002：与现有行为一致）"""
    resolver = ToolAccessResolver()
    specs = [
        _make_spec("t1", requires_capabilities=[("exam", "read")]),
    ]
    result = resolver.resolve(specs, role="admin", enabled_modules=None, capabilities={})
    assert len(result) == 1  # 空 caps → 默认允许
