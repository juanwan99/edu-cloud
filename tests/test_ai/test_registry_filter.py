import pytest
from edu_cloud.ai.registry import ToolRegistry
from edu_cloud.ai.tool_context import ToolContext, ToolResult


@pytest.fixture
def registry_with_tools():
    reg = ToolRegistry()

    @reg.register(name="tool_a", description="Tool A")
    async def tool_a(input_data: dict, ctx: ToolContext) -> ToolResult:
        return ToolResult(success=True, data="a")

    @reg.register(name="tool_b", description="Tool B")
    async def tool_b(input_data: dict, ctx: ToolContext) -> ToolResult:
        return ToolResult(success=True, data="b")

    @reg.register(name="tool_c", description="Tool C")
    async def tool_c(input_data: dict, ctx: ToolContext) -> ToolResult:
        return ToolResult(success=True, data="c")

    return reg


class TestFilterByNames:
    def test_filter_subset(self, registry_with_tools):
        result = registry_with_tools.filter_by_names(["tool_a", "tool_c"])
        names = [s.name for s in result]
        assert names == ["tool_a", "tool_c"]

    def test_filter_all(self, registry_with_tools):
        result = registry_with_tools.filter_by_names(["tool_a", "tool_b", "tool_c"])
        assert len(result) == 3

    def test_filter_empty(self, registry_with_tools):
        result = registry_with_tools.filter_by_names([])
        assert result == []

    def test_filter_nonexistent(self, registry_with_tools):
        result = registry_with_tools.filter_by_names(["tool_a", "nonexistent"])
        names = [s.name for s in result]
        assert names == ["tool_a"]

    def test_filter_preserves_order(self, registry_with_tools):
        result = registry_with_tools.filter_by_names(["tool_c", "tool_a"])
        names = [s.name for s in result]
        assert names == ["tool_c", "tool_a"]

    def test_get_all_specs_unchanged(self, registry_with_tools):
        all_specs = registry_with_tools.get_all_specs()
        assert len(all_specs) == 3
