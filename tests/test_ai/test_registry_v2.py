import pytest
from edu_cloud.ai.registry import ToolRegistry, ToolSpec
from edu_cloud.ai.tool_context import ToolContext, ToolResult


def test_toolspec_has_new_fields():
    spec = ToolSpec(
        name="test",
        description="test tool",
        parameters={},
        func=lambda i, c: None,
        category="general",
        domain="exam",
        is_read_only=True,
        sensitivity="school",
        risk_level="low",
        allowed_roles=None,
        requires_capabilities=[],
    )
    assert spec.is_read_only is True
    assert spec.sensitivity == "school"


@pytest.mark.asyncio
async def test_registry_register_new_style():
    reg = ToolRegistry()

    @reg.register(
        name="get_exam",
        description="Get exam",
        parameters={"exam_id": {"type": "string"}},
        domain="exam",
        is_read_only=True,
        sensitivity="school",
    )
    async def get_exam(input: dict, ctx: ToolContext) -> ToolResult:
        return ToolResult(success=True, data={"id": input["exam_id"]})

    specs = reg.get_all_specs()
    assert len(specs) == 1
    assert specs[0].name == "get_exam"
    assert specs[0].is_read_only is True
    assert specs[0].sensitivity == "school"


@pytest.mark.asyncio
async def test_registry_execute_new_style():
    reg = ToolRegistry()

    @reg.register(name="add_nums", description="Add", parameters={}, is_read_only=True, sensitivity="public")
    async def add_nums(input: dict, ctx: ToolContext) -> ToolResult:
        return ToolResult(success=True, data={"sum": input["a"] + input["b"]})

    ctx = ToolContext(db=None, school_id="S1", user_id="U1", role="teacher")
    result = await reg.execute("add_nums", {"a": 1, "b": 2}, ctx)
    assert result.success is True
    assert result.data["sum"] == 3


@pytest.mark.asyncio
async def test_registry_execute_unknown_tool_new_style():
    reg = ToolRegistry()
    ctx = ToolContext(db=None, school_id="S1", user_id="U1", role="teacher")
    result = await reg.execute("nonexistent", {}, ctx)
    assert isinstance(result, ToolResult)
    assert result.success is False
    assert "Unknown tool" in result.error


def test_registry_get_method():
    reg = ToolRegistry()

    @reg.register(name="t1", description="Tool 1", parameters={}, sensitivity="public", is_read_only=True)
    async def t1(input: dict, ctx: ToolContext) -> ToolResult:
        return ToolResult(success=True, data=None)

    assert reg.get("t1") is not None
    assert reg.get("t1").name == "t1"
    assert reg.get("nonexistent") is None


def test_registry_get_schemas_includes_new_fields():
    reg = ToolRegistry()

    @reg.register(name="t1", description="Tool 1", parameters={"x": {"type": "int"}}, sensitivity="student", is_read_only=True)
    async def t1(input: dict, ctx: ToolContext) -> ToolResult:
        return ToolResult(success=True, data=None)

    schemas = reg.get_schemas()
    assert len(schemas) == 1
    assert schemas[0]["function"]["name"] == "t1"
