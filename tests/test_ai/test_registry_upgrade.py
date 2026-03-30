import pytest
from edu_cloud.ai.registry import ToolRegistry, ToolSpec


def test_toolspec_has_metadata_fields():
    spec = ToolSpec(
        name="test_tool",
        description="A test",
        parameters={},
        func=lambda: None,
        module_code="exam",
        domain="analytics",
        risk_level="low",
        allowed_roles=["platform_admin"],
        requires_capabilities=[("exam", "read")],
    )
    assert spec.module_code == "exam"
    assert spec.domain == "analytics"
    assert spec.risk_level == "low"
    assert spec.allowed_roles == ["platform_admin"]
    assert spec.requires_capabilities == [("exam", "read")]


def test_toolspec_defaults():
    spec = ToolSpec(name="t", description="d", parameters={}, func=lambda: None)
    assert spec.module_code is None
    assert spec.domain == "general"
    assert spec.risk_level == "low"
    assert spec.allowed_roles is None
    assert spec.requires_capabilities == []


def test_register_with_metadata():
    reg = ToolRegistry()

    @reg.register(
        name="my_tool",
        description="Test",
        parameters={"type": "object", "properties": {}},
        module_code="exam",
        domain="analytics",
        risk_level="med",
    )
    async def my_tool():
        return {}

    specs = reg.get_all_specs()
    assert len(specs) == 1
    assert specs[0].module_code == "exam"
    assert specs[0].domain == "analytics"


def test_register_backward_compat():
    """现有 category 参数仍可用"""
    reg = ToolRegistry()

    @reg.register(
        name="old_tool",
        description="Legacy",
        parameters={},
        category="L1_exam",
    )
    async def old_tool():
        return {}

    specs = reg.get_all_specs()
    assert specs[0].category == "L1_exam"
    assert specs[0].domain == "general"  # 未指定 domain 时默认


def test_get_schemas_still_works():
    """确保现有 get_schemas(categories=...) 不崩溃"""
    reg = ToolRegistry()

    @reg.register(name="t1", description="d", parameters={}, category="L1_exam")
    async def t1():
        return {}

    schemas = reg.get_schemas(categories=["L1_exam"])
    assert len(schemas) == 1
    assert schemas[0]["function"]["name"] == "t1"
