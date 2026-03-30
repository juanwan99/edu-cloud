"""Verify all 25+ tools are registered and category/metadata structure is correct."""
import pytest
from edu_cloud.ai.registry import tools
from edu_cloud.ai.tool_access import ToolAccessResolver
import edu_cloud.ai.tools  # noqa: F401 — trigger registration


def test_total_tool_count():
    """All tool modules register the expected total (≥25 tools)."""
    all_tools = tools.list_tools()
    assert len(all_tools) >= 25, f"Expected ≥25 tools, got {len(all_tools)}: {all_tools}"


def test_tool_categories_present():
    """All 9 expected categories have at least one tool."""
    expected_categories = {
        "L1_exam", "L1_student",
        "L2_analytics", "L2_cross_school",
        "L3_knowledge", "L3_knowledge_db",
        "L4_action", "L5_bank", "L6_profile",
    }
    found_categories = set()
    for name in tools.list_tools():
        cat = tools._tools[name].category
        found_categories.add(cat)
    for cat in expected_categories:
        assert cat in found_categories, f"Category {cat} has no tools"


@pytest.mark.asyncio
async def test_platform_admin_gets_all_tools():
    """platform_admin 通过 ToolAccessResolver 看到所有工具。"""
    resolver = ToolAccessResolver()
    # 启用所有模块（模拟完整学校配置）
    all_modules = {"exam", "grading", "homework", "study_analytics", "research", "teaching", "calendar", "studio"}
    result = await resolver.resolve(
        all_specs=tools.get_all_specs(), role="platform_admin",
        enabled_modules=all_modules, capabilities={},
    )
    assert len(result) >= 25


@pytest.mark.asyncio
async def test_resolver_filters_by_allowed_roles():
    """ToolAccessResolver 按 allowed_roles 过滤。"""
    from edu_cloud.ai.registry import ToolSpec
    from unittest.mock import AsyncMock

    specs = [
        ToolSpec(name="open", description="open", parameters={}, func=AsyncMock(), allowed_roles=None),
        ToolSpec(name="admin_only", description="admin", parameters={}, func=AsyncMock(),
                 allowed_roles=["platform_admin"]),
    ]
    resolver = ToolAccessResolver()
    # district_admin 看不到 admin_only
    result = await resolver.resolve(all_specs=specs, role="district_admin",
                                     enabled_modules=set(), capabilities={})
    assert len(result) == 1
    assert result[0].name == "open"


def test_empty_categories_no_tools():
    """Empty category list means no tool access via get_schemas."""
    schemas = tools.get_schemas(categories=[])
    assert len(schemas) == 0


def test_get_all_specs_returns_toolspec():
    """get_all_specs() returns ToolSpec objects with correct fields."""
    specs = tools.get_all_specs()
    assert len(specs) >= 25
    for spec in specs:
        assert hasattr(spec, "name")
        assert hasattr(spec, "domain")
        assert hasattr(spec, "allowed_roles")
        assert hasattr(spec, "module_code")
        assert hasattr(spec, "risk_level")
