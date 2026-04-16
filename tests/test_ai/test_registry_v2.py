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


def test_registry_get_schemas_new_style_wraps_parameters():
    """F001: new-style parameters (properties-only dict) are wrapped in JSON Schema object."""
    reg = ToolRegistry()

    @reg.register(name="t1", description="Tool 1", parameters={"x": {"type": "int"}}, sensitivity="student", is_read_only=True)
    async def t1(input: dict, ctx: ToolContext) -> ToolResult:
        return ToolResult(success=True, data=None)

    schemas = reg.get_schemas()
    assert len(schemas) == 1
    assert schemas[0]["function"]["name"] == "t1"
    params = schemas[0]["function"]["parameters"]
    # New-style: properties-only dict wrapped into {"type": "object", "properties": {...}}
    assert params["type"] == "object"
    assert "x" in params["properties"]
    assert params["properties"]["x"] == {"type": "int"}


def test_registry_get_schemas_legacy_not_double_wrapped():
    """F001: legacy full JSON Schema parameters are NOT double-wrapped."""
    reg = ToolRegistry()

    legacy_params = {
        "type": "object",
        "properties": {"a": {"type": "number"}, "b": {"type": "number"}},
        "required": ["a", "b"],
    }

    @reg.register(name="legacy", description="Legacy tool", parameters=legacy_params, is_read_only=True, sensitivity="school")
    async def legacy(input: dict, ctx: ToolContext) -> ToolResult:
        return ToolResult(success=True, data=None)

    schemas = reg.get_schemas()
    params = schemas[0]["function"]["parameters"]
    # Legacy: passed through as-is, not wrapped again
    assert params["type"] == "object"
    assert "a" in params["properties"]
    assert "required" in params  # legacy schema has "required" at top level


@pytest.mark.asyncio
async def test_registry_execute_new_style_exception():
    """F002: new-style tool that raises exception returns ToolResult(success=False)."""
    reg = ToolRegistry()

    @reg.register(name="boom", description="Boom", parameters={}, is_read_only=True, sensitivity="public")
    async def boom(input: dict, ctx: ToolContext) -> ToolResult:
        raise RuntimeError("tool exploded")

    ctx = ToolContext(db=None, school_id="S1", user_id="U1", role="teacher")
    result = await reg.execute("boom", {}, ctx)
    assert isinstance(result, ToolResult)
    assert result.success is False
    assert "tool exploded" in result.error


@pytest.mark.asyncio
async def test_registry_execute_legacy_exception():
    """F002: legacy tool that raises exception returns {"error": ...}."""
    reg = ToolRegistry()

    @reg.register(name="legacy_boom", description="Boom", parameters={}, is_read_only=True, sensitivity="public")
    async def legacy_boom(x: int, _db=None) -> dict:
        raise ValueError("bad input")

    result = await reg.execute("legacy_boom", {"x": 1}, _db="mock")
    assert isinstance(result, dict)
    assert "error" in result
    assert "bad input" in result["error"]
