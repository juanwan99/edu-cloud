"""AgentLoop core tests — plan/thinking/sensitivity/memory (Task 13)."""
import json
import pytest
from unittest.mock import AsyncMock, MagicMock
from edu_cloud.ai.agent_loop import AgentLoop, AgentState
from edu_cloud.ai.llm_adapter import LLMProxyAdapter, LLMResponse, TokenUsage
from edu_cloud.ai.registry import ToolRegistry
from edu_cloud.ai.tool_context import ToolContext, ToolResult
from edu_cloud.ai.schemas import Message, ToolCall, Transition, AgentEvent
from edu_cloud.ai.capability_probe import LoopStrategy


def _setup():
    reg = ToolRegistry()

    @reg.register(name="get_score", description="Get score", parameters={"exam_id": {"type": "string"}},
                  is_read_only=True, sensitivity="school")
    async def get_score(input: dict, ctx: ToolContext) -> ToolResult:
        return ToolResult(success=True, data={"avg": 85.2})

    ctx = ToolContext(db=None, school_id="S1", user_id="U1", role="academic_director")
    return reg, ctx


@pytest.mark.asyncio
async def test_simple_answer():
    """LLM returns direct answer, no tools."""
    reg, ctx = _setup()
    adapter = LLMProxyAdapter(base_url="http://test:8100", slot="primary")
    adapter.chat = AsyncMock(return_value=LLMResponse(
        content="数学平均分是 85.2 分",
        usage=TokenUsage(50, 30),
        stop_reason="end_turn",
    ))

    loop = AgentLoop(registry=reg, adapter=adapter, strategy=LoopStrategy.for_tier(3))
    events = []
    async for event in loop.run("数学平均分", ctx, tool_specs=reg.get_all_specs()):
        events.append(event)

    types = [e.type for e in events]
    assert "answer" in types
    assert "done" in types
    answer_event = next(e for e in events if e.type == "answer")
    assert "85.2" in answer_event.data["content"]


@pytest.mark.asyncio
async def test_tool_call_and_answer():
    """LLM calls a tool, then answers."""
    reg, ctx = _setup()
    adapter = LLMProxyAdapter(base_url="http://test:8100", slot="primary")

    call_count = 0
    async def mock_chat(request):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            return LLMResponse(
                tool_calls=[ToolCall(id="tc1", name="get_score", arguments={"exam_id": "E1"}, _raw={})],
                usage=TokenUsage(50, 30),
                stop_reason="tool_use",
            )
        return LLMResponse(
            content="平均分是 85.2",
            usage=TokenUsage(80, 40),
            stop_reason="end_turn",
        )

    adapter.chat = mock_chat

    loop = AgentLoop(registry=reg, adapter=adapter, strategy=LoopStrategy.for_tier(3))
    events = []
    async for event in loop.run("查考试成绩", ctx, tool_specs=reg.get_all_specs()):
        events.append(event)

    types = [e.type for e in events]
    assert "tool_call" in types
    assert "tool_result" in types
    assert "answer" in types


@pytest.mark.asyncio
async def test_max_turns_stops():
    """Loop stops when max_turns is reached."""
    reg, ctx = _setup()
    adapter = LLMProxyAdapter(base_url="http://test:8100", slot="primary")
    # Always return tool_call, never answer
    adapter.chat = AsyncMock(return_value=LLMResponse(
        tool_calls=[ToolCall(id="tc1", name="get_score", arguments={"exam_id": "E1"}, _raw={})],
        usage=TokenUsage(10, 5),
        stop_reason="tool_use",
    ))

    strategy = LoopStrategy.for_tier(3)  # max_turns=8
    loop = AgentLoop(registry=reg, adapter=adapter, strategy=strategy)
    events = []
    async for event in loop.run("loop forever", ctx, tool_specs=reg.get_all_specs()):
        events.append(event)

    types = [e.type for e in events]
    assert "done" in types
    done_event = next(e for e in events if e.type == "done")
    assert done_event.data["turns"] <= strategy.max_turns + 1


@pytest.mark.asyncio
async def test_plan_branch():
    """Tier ≤ 2: AgentLoop produces plan + task_update events when planner returns a plan."""
    import json as _json
    reg, ctx = _setup()
    adapter = LLMProxyAdapter(base_url="http://test:8100", slot="primary")

    plan_json = _json.dumps({"plan": [
        {"description": "收集成绩", "tools_hint": ["get_score"], "depends_on": []},
    ]})
    call_count = 0
    async def mock_chat(request):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            # Planner call — returns plan
            return LLMResponse(content=plan_json, usage=TokenUsage(30, 20))
        if call_count == 2:
            # Task execution — tool call
            return LLMResponse(
                tool_calls=[ToolCall(id="tc1", name="get_score", arguments={"exam_id": "E1"}, _raw={})],
                usage=TokenUsage(20, 10), stop_reason="tool_use",
            )
        # Final answer
        return LLMResponse(content="分析完成", usage=TokenUsage(20, 10), stop_reason="end_turn")

    adapter.chat = mock_chat

    strategy = LoopStrategy.for_tier(2)  # task_planning=True
    loop = AgentLoop(registry=reg, adapter=adapter, strategy=strategy)
    events = []
    async for event in loop.run("全面分析三年级", ctx, tool_specs=reg.get_all_specs()):
        events.append(event)

    types = [e.type for e in events]
    assert "plan" in types, f"Expected 'plan' event, got: {types}"
    assert "task_update" in types, f"Expected 'task_update' event, got: {types}"
    assert "done" in types


@pytest.mark.asyncio
async def test_thinking_event():
    """When LLM returns content alongside tool_calls, emit a thinking event."""
    reg, ctx = _setup()
    adapter = LLMProxyAdapter(base_url="http://test:8100", slot="primary")

    call_count = 0
    async def mock_chat(request):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            return LLMResponse(
                content="让我查一下成绩...",
                tool_calls=[ToolCall(id="tc1", name="get_score", arguments={"exam_id": "E1"}, _raw={})],
                usage=TokenUsage(30, 20), stop_reason="tool_use",
            )
        return LLMResponse(content="平均分 85.2", usage=TokenUsage(20, 10), stop_reason="end_turn")

    adapter.chat = mock_chat

    strategy = LoopStrategy.for_tier(3)
    loop = AgentLoop(registry=reg, adapter=adapter, strategy=strategy)
    events = []
    async for event in loop.run("查成绩", ctx, tool_specs=reg.get_all_specs()):
        events.append(event)

    types = [e.type for e in events]
    assert "thinking" in types, f"Expected 'thinking' event when content + tool_calls, got: {types}"


@pytest.mark.asyncio
async def test_error_count_threshold():
    """error_count >= 3 → yield error event and stop."""
    reg, ctx = _setup()
    adapter = LLMProxyAdapter(base_url="http://test:8100", slot="primary")
    adapter.chat = AsyncMock(side_effect=Exception("connection refused"))

    strategy = LoopStrategy.for_tier(3)
    loop = AgentLoop(registry=reg, adapter=adapter, strategy=strategy)
    events = []
    async for event in loop.run("test", ctx, tool_specs=reg.get_all_specs()):
        events.append(event)

    types = [e.type for e in events]
    assert "error" in types
    assert "done" in types
