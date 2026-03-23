import pytest
from edu_cloud.ai.registry import ToolRegistry

registry = ToolRegistry()

@registry.register(
    name="test_add", description="两数相加",
    parameters={"type": "object", "properties": {"a": {"type": "number"}, "b": {"type": "number"}}, "required": ["a", "b"]},
    category="test",
)
async def _add_func(a: float, b: float, _db=None) -> dict:
    return {"result": a + b}

def test_register_tool():
    assert "test_add" in registry.list_tools()

def test_get_schemas():
    schemas = registry.get_schemas()
    assert len(schemas) >= 1
    schema = next(s for s in schemas if s["function"]["name"] == "test_add")
    assert schema["type"] == "function"
    assert "a" in schema["function"]["parameters"]["properties"]

def test_get_schemas_filtered_by_category():
    schemas = registry.get_schemas(categories=["test"])
    assert len(schemas) >= 1
    schemas_other = registry.get_schemas(categories=["nonexistent"])
    assert len(schemas_other) == 0

@pytest.mark.asyncio
async def test_execute_tool():
    result = await registry.execute("test_add", {"a": 3, "b": 5})
    assert result == {"result": 8}

@pytest.mark.asyncio
async def test_execute_with_injected_params():
    result = await registry.execute("test_add", {"a": 1, "b": 2}, _db="mock_db")
    assert result == {"result": 3}

def test_execute_unknown_tool():
    with pytest.raises(KeyError):
        import asyncio
        asyncio.get_event_loop().run_until_complete(registry.execute("nonexistent", {}))


# ── Integration tests: real global registry with real tools ──────────────


def test_real_registry_tool_visibility():
    """Cross-school analytics tools are visible via L2_cross_school category."""
    from edu_cloud.ai.registry import tools
    import edu_cloud.ai.tools  # noqa: F401 — trigger registration

    schemas = tools.get_schemas(categories=["L2_cross_school"])
    tool_names = [s["function"]["name"] for s in schemas]
    assert "get_exam_scores" in tool_names
    assert "get_class_stats" in tool_names
    assert len(tool_names) >= 2


def test_real_registry_empty_categories_no_tools():
    """Empty categories list (e.g. parent role) returns zero tools."""
    from edu_cloud.ai.registry import tools
    import edu_cloud.ai.tools  # noqa: F401

    schemas = tools.get_schemas(categories=[])
    assert len(schemas) == 0


def test_real_registry_wrong_category_no_tools():
    """Non-matching category returns zero analytics tools."""
    from edu_cloud.ai.registry import tools
    import edu_cloud.ai.tools  # noqa: F401

    schemas = tools.get_schemas(categories=["nonexistent_category"])
    assert len(schemas) == 0
