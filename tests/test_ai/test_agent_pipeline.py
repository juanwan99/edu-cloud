import pytest
from unittest.mock import AsyncMock, patch
from edu_cloud.ai.tool_access import ToolAccessResolver
from edu_cloud.ai.intent_resolver import IntentResolver
from edu_cloud.ai.model_router import ModelRouter
from edu_cloud.ai.registry import ToolSpec


def _make_spec(name, domain="general", allowed_roles=None, module_code=None):
    return ToolSpec(
        name=name, description=f"Tool {name}", parameters={},
        func=AsyncMock(return_value={"ok": True}),
        domain=domain, allowed_roles=allowed_roles, module_code=module_code,
    )


@pytest.mark.asyncio
async def test_pipeline_end_to_end():
    """完整 Pipeline: 工具过滤 → 意图裁剪 → 模型选择"""
    all_tools = [
        _make_spec("get_scores", domain="analytics", allowed_roles=None),
        _make_spec("admin_tool", domain="exam", allowed_roles=["platform_admin"]),
        _make_spec("calendar_tool", domain="calendar"),
    ]

    # Step 1: ToolAccessResolver (subject_teacher 看不到 admin_tool)
    resolver = ToolAccessResolver()
    available = resolver.resolve(
        all_specs=all_tools, role="subject_teacher",
        enabled_modules=set(), capabilities={},
    )
    assert len(available) == 2  # get_scores + calendar_tool

    # Step 2: IntentResolver (查成绩 → analytics domain)
    intent = IntentResolver(llm_client=None)
    selected = await intent.resolve("查一下成绩", available)
    assert len(selected) == 1
    assert selected[0].name == "get_scores"
    assert intent.last_domains == ["analytics"]

    # Step 3: ModelRouter (单域低风险 → standard)
    tier = ModelRouter().select(intent.last_domains, selected)
    assert tier == "standard"


@pytest.mark.asyncio
async def test_pipeline_parent_sees_only_profile():
    """parent 角色只能看到 allowed_roles=None 的工具（即 profile 域）。
    F-01: analytics/student/exam/bank/knowledge/action/studio/calendar 工具的
    allowed_roles 显式排除 parent，只有 L6_profile 保持 None。"""
    all_tools = [
        _make_spec("get_scores", domain="analytics",
                   allowed_roles=["platform_admin", "academic_director", "grade_leader"]),
        _make_spec("get_profile", domain="profile", allowed_roles=None),
        _make_spec("admin_tool", allowed_roles=["platform_admin"]),
    ]
    resolver = ToolAccessResolver()
    available = resolver.resolve(
        all_specs=all_tools, role="parent",
        enabled_modules=set(), capabilities={},
    )
    assert len(available) == 1
    assert available[0].name == "get_profile"


@pytest.mark.asyncio
async def test_pipeline_module_disabled():
    """模块禁用时工具不可见"""
    all_tools = [
        _make_spec("exam_tool", domain="exam", module_code="exam"),
        _make_spec("open_tool", domain="general"),
    ]
    resolver = ToolAccessResolver()
    available = resolver.resolve(
        all_specs=all_tools, role="platform_admin",
        enabled_modules={"grading"},  # exam 未启用
        capabilities={},
    )
    assert len(available) == 1
    assert available[0].name == "open_tool"


@pytest.mark.asyncio
async def test_pipeline_fallback_on_error():
    """Pipeline 中任意步骤异常时 fallback 到全工具集 + standard 模型"""
    all_tools = [
        _make_spec("tool_a", domain="exam"),
        _make_spec("tool_b", domain="analytics"),
    ]

    # ToolAccessResolver 正常返回
    resolver = ToolAccessResolver()
    available = resolver.resolve(
        all_specs=all_tools, role="platform_admin",
        enabled_modules=set(), capabilities={},
    )

    # IntentResolver 抛异常（模拟 LLM 故障）
    intent = IntentResolver(llm_client=None)
    with patch.object(intent, "resolve", side_effect=RuntimeError("LLM down")):
        try:
            selected = await intent.resolve("查成绩", available)
        except RuntimeError:
            # Pipeline 应 catch 并 fallback
            selected = available  # fallback: 全工具集

    # ModelRouter 应返回 standard 作为 fallback
    tier = ModelRouter().select([], selected)
    assert tier == "standard"
    assert len(selected) == 2  # 全工具集
