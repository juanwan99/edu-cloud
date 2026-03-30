import pytest
from unittest.mock import AsyncMock
from edu_cloud.ai.tool_access import ToolAccessResolver
from edu_cloud.ai.registry import ToolSpec


def _make_spec(name, category="general", module_code=None, domain="general",
               allowed_roles=None, requires_capabilities=None):
    return ToolSpec(
        name=name, description=f"Tool {name}", parameters={},
        func=AsyncMock(), category=category, module_code=module_code,
        domain=domain, allowed_roles=allowed_roles,
        requires_capabilities=requires_capabilities or [],
    )


@pytest.mark.asyncio
async def test_rbac_filter_blocks_unauthorized_role():
    specs = [
        _make_spec("admin_only", allowed_roles=["platform_admin"]),
        _make_spec("open_tool", allowed_roles=None),
    ]
    resolver = ToolAccessResolver()
    result = await resolver.resolve(
        all_specs=specs, role="subject_teacher",
        enabled_modules=set(), capabilities={},
    )
    assert len(result) == 1
    assert result[0].name == "open_tool"


@pytest.mark.asyncio
async def test_module_filter_blocks_disabled_module():
    specs = [
        _make_spec("exam_tool", module_code="exam"),
        _make_spec("no_module_tool"),
    ]
    resolver = ToolAccessResolver()
    result = await resolver.resolve(
        all_specs=specs, role="platform_admin",
        enabled_modules={"grading"},  # exam 未启用
        capabilities={},
    )
    assert len(result) == 1
    assert result[0].name == "no_module_tool"


@pytest.mark.asyncio
async def test_capability_filter_blocks_denied():
    specs = [
        _make_spec("cap_tool", requires_capabilities=[("exam", "read")]),
        _make_spec("no_cap_tool"),
    ]
    resolver = ToolAccessResolver()
    result = await resolver.resolve(
        all_specs=specs, role="platform_admin",
        enabled_modules=set(),
        capabilities={("exam", "read"): False},  # 显式拒绝
    )
    assert len(result) == 1
    assert result[0].name == "no_cap_tool"


@pytest.mark.asyncio
async def test_capability_default_allow():
    """未配置的 capability 默认允许"""
    specs = [_make_spec("cap_tool", requires_capabilities=[("exam", "read")])]
    resolver = ToolAccessResolver()
    result = await resolver.resolve(
        all_specs=specs, role="platform_admin",
        enabled_modules=set(), capabilities={},  # 未配置
    )
    assert len(result) == 1


@pytest.mark.asyncio
async def test_triple_filter_combined():
    specs = [
        _make_spec("full", allowed_roles=["academic_director"],
                   module_code="exam", requires_capabilities=[("exam", "write")]),
        _make_spec("open"),
    ]
    resolver = ToolAccessResolver()
    # 角色匹配 + 模块启用 + capability 允许
    result = await resolver.resolve(
        all_specs=specs, role="academic_director",
        enabled_modules={"exam"},
        capabilities={("exam", "write"): True},
    )
    assert len(result) == 2


@pytest.mark.asyncio
async def test_empty_specs():
    resolver = ToolAccessResolver()
    result = await resolver.resolve(
        all_specs=[], role="platform_admin",
        enabled_modules=set(), capabilities={},
    )
    assert result == []


@pytest.mark.asyncio
async def test_platform_admin_sees_all_role_restricted():
    """platform_admin 在 allowed_roles 列表中时能看到"""
    specs = [_make_spec("restricted", allowed_roles=["platform_admin"])]
    resolver = ToolAccessResolver()
    result = await resolver.resolve(
        all_specs=specs, role="platform_admin",
        enabled_modules=set(), capabilities={},
    )
    assert len(result) == 1


@pytest.mark.asyncio
async def test_enabled_modules_none_skips_module_filter():
    """CR-05: enabled_modules=None 时跳过模块过滤（platform_admin 无 school_id）"""
    specs = [
        _make_spec("grading_tool", module_code="grading"),
        _make_spec("exam_tool", module_code="exam"),
        _make_spec("no_module_tool"),
    ]
    resolver = ToolAccessResolver()
    result = await resolver.resolve(
        all_specs=specs, role="platform_admin",
        enabled_modules=None,  # platform_admin: 不过滤模块
        capabilities={},
    )
    assert len(result) == 3
    names = {s.name for s in result}
    assert "grading_tool" in names
    assert "exam_tool" in names
    assert "no_module_tool" in names
