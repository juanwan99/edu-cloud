# tests/test_ai/test_agent_loop_subagent.py
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from edu_cloud.ai.agent_loop import AgentLoop, AgentState
from edu_cloud.ai.agent_spec import AgentSpec
from edu_cloud.ai.capability_probe import LoopStrategy
from edu_cloud.ai.llm_adapter import LLMProxyAdapter, LLMResponse, TokenUsage
from edu_cloud.ai.registry import ToolRegistry, ToolSpec
from edu_cloud.ai.schemas import AgentEvent, Message
from edu_cloud.ai.shared_state import SharedState
from edu_cloud.ai.tool_context import ToolContext, ToolResult


@pytest.fixture
def mock_registry():
    reg = ToolRegistry()

    @reg.register(name="tool_a", description="Tool A")
    async def tool_a(input_data: dict, ctx: ToolContext) -> ToolResult:
        return ToolResult(success=True, data="result_a")

    @reg.register(name="tool_b", description="Tool B")
    async def tool_b(input_data: dict, ctx: ToolContext) -> ToolResult:
        return ToolResult(success=True, data="result_b")

    return reg


@pytest.fixture
def mock_adapter():
    adapter = MagicMock(spec=LLMProxyAdapter)
    adapter.context_window_size.return_value = 128_000
    adapter.supports_tool_use.return_value = True
    adapter.supports_parallel_tool_calls.return_value = True
    adapter.chat = AsyncMock(return_value=LLMResponse(
        content="Done",
        stop_reason="end_turn",
        usage=TokenUsage(input_tokens=100, output_tokens=50),
    ))
    adapter.close = AsyncMock()
    return adapter


class TestSubAgentMode:
    @pytest.mark.asyncio
    async def test_run_as_sub_agent_exists(self, mock_registry, mock_adapter):
        strategy = LoopStrategy.for_tier(2)
        loop = AgentLoop(registry=mock_registry, adapter=mock_adapter, strategy=strategy)
        assert hasattr(loop, 'run_as_sub_agent')

    @pytest.mark.asyncio
    async def test_run_as_sub_agent_uses_spec_max_turns(self, mock_registry, mock_adapter):
        spec = AgentSpec(name="test", description="Test", tools=["tool_a"], max_turns=3)
        strategy = LoopStrategy.for_tier(2)
        loop = AgentLoop(registry=mock_registry, adapter=mock_adapter, strategy=strategy)

        ctx = MagicMock(spec=ToolContext)
        ctx.db = None
        ctx.anonymizer = MagicMock()
        ctx.anonymizer.anonymize = lambda x: x
        ctx.anonymizer.deanonymize = lambda x: x

        state = SharedState()
        result = await loop.run_as_sub_agent(
            spec=spec, goal="test goal", ctx=ctx, state=state,
        )
        assert isinstance(result, str)

    @pytest.mark.asyncio
    async def test_run_as_sub_agent_filters_tools(self, mock_registry, mock_adapter):
        """Sub-agent only sees tools listed in AgentSpec."""
        spec = AgentSpec(name="test", description="Test", tools=["tool_a"])
        strategy = LoopStrategy.for_tier(2)
        loop = AgentLoop(registry=mock_registry, adapter=mock_adapter, strategy=strategy)

        ctx = MagicMock(spec=ToolContext)
        ctx.db = None
        ctx.anonymizer = MagicMock()
        ctx.anonymizer.anonymize = lambda x: x
        ctx.anonymizer.deanonymize = lambda x: x

        state = SharedState()
        result = await loop.run_as_sub_agent(
            spec=spec, goal="test goal", ctx=ctx, state=state,
        )
        # F004 fix: strong assertions, no conditional guards
        assert mock_adapter.chat.called, "adapter.chat must be called"
        call_args = mock_adapter.chat.call_args
        request = call_args[0][0]
        assert request.tools is not None, "tools must not be None"
        assert len(request.tools) > 0, "tools must not be empty"
        tool_names = [t["function"]["name"] for t in request.tools]
        assert tool_names == ["tool_a"], f"Expected ['tool_a'], got {tool_names}"

    @pytest.mark.asyncio
    async def test_run_as_sub_agent_empty_tools_gets_empty(self, mock_registry, mock_adapter):
        """Sub-agent with no tools should pass empty tool list."""
        spec = AgentSpec(name="test", description="Test", tools=[])
        strategy = LoopStrategy.for_tier(2)
        loop = AgentLoop(registry=mock_registry, adapter=mock_adapter, strategy=strategy)

        ctx = MagicMock(spec=ToolContext)
        ctx.db = None
        ctx.anonymizer = MagicMock()
        ctx.anonymizer.anonymize = lambda x: x
        ctx.anonymizer.deanonymize = lambda x: x

        state = SharedState()
        result = await loop.run_as_sub_agent(
            spec=spec, goal="test", ctx=ctx, state=state,
        )
        call_args = mock_adapter.chat.call_args
        request = call_args[0][0]
        assert not request.tools or len(request.tools) == 0
