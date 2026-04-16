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

    # INV-004: verify exact backward-compatible payload shape
    tc_event = next(e for e in events if e.type == "tool_call")
    assert tc_event.data == {"tool": "get_score", "arguments": {"exam_id": "E1"}}, \
        f"tool_call payload must match old agent.py format, got: {tc_event.data}"
    tr_event = next(e for e in events if e.type == "tool_result")
    assert tr_event.data == {"tool": "get_score", "result": {"avg": 85.2}}, \
        f"tool_result payload must match old agent.py format, got: {tr_event.data}"


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
async def test_plan_multi_task():
    """F004: Multi-task plan produces task_update for each task and a final answer."""
    import json as _json
    reg, ctx = _setup()
    adapter = LLMProxyAdapter(base_url="http://test:8100", slot="primary")

    plan_json = _json.dumps({"plan": [
        {"description": "收集成绩", "tools_hint": ["get_score"], "depends_on": []},
        {"description": "生成总结", "tools_hint": [], "depends_on": ["0"]},
    ]})
    call_count = 0
    async def mock_chat(request):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            # Planner call — returns 2-task plan
            return LLMResponse(content=plan_json, usage=TokenUsage(30, 20))
        if call_count == 2:
            # Task 0: tool call
            return LLMResponse(
                tool_calls=[ToolCall(id="tc1", name="get_score", arguments={"exam_id": "E1"}, _raw={})],
                usage=TokenUsage(20, 10), stop_reason="tool_use",
            )
        if call_count == 3:
            # Task 0: answer (complete task 0)
            return LLMResponse(content="成绩已收集", usage=TokenUsage(20, 10), stop_reason="end_turn")
        # Task 1: final summary answer
        return LLMResponse(content="综合分析：数学平均分 85.2，表现良好", usage=TokenUsage(30, 20), stop_reason="end_turn")

    adapter.chat = mock_chat

    strategy = LoopStrategy.for_tier(2)
    loop = AgentLoop(registry=reg, adapter=adapter, strategy=strategy)
    events = []
    async for event in loop.run("全面分析三年级", ctx, tool_specs=reg.get_all_specs()):
        events.append(event)

    types = [e.type for e in events]
    # Must have plan, two task_updates (in_progress), and answer
    assert "plan" in types
    task_updates = [e for e in events if e.type == "task_update"]
    in_progress_updates = [e for e in task_updates if e.data.get("status") == "in_progress"]
    assert len(in_progress_updates) >= 2, f"Expected 2+ in_progress task_updates, got {len(in_progress_updates)}"
    assert "answer" in types
    answer_event = next(e for e in events if e.type == "answer")
    assert "综合" in answer_event.data["content"] or "分析" in answer_event.data["content"]
    assert "done" in types


@pytest.mark.asyncio
async def test_tool_failure_result_format():
    """R3-02: tool_result on failure must emit {"tool": ..., "result": {"error": ...}}."""
    reg = ToolRegistry()

    @reg.register(name="fail_tool", description="Always fails", parameters={},
                  is_read_only=True, sensitivity="school")
    async def fail_tool(input: dict, ctx: ToolContext) -> ToolResult:
        return ToolResult(success=False, error="tool execution failed")

    ctx = ToolContext(db=None, school_id="S1", user_id="U1", role="academic_director")
    adapter = LLMProxyAdapter(base_url="http://test:8100", slot="primary")

    call_count = 0
    async def mock_chat(request):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            return LLMResponse(
                tool_calls=[ToolCall(id="tc1", name="fail_tool", arguments={}, _raw={})],
                usage=TokenUsage(20, 10), stop_reason="tool_use",
            )
        return LLMResponse(content="工具失败了", usage=TokenUsage(20, 10), stop_reason="end_turn")

    adapter.chat = mock_chat

    loop = AgentLoop(registry=reg, adapter=adapter, strategy=LoopStrategy.for_tier(3))
    events = []
    async for event in loop.run("test", ctx, tool_specs=reg.get_all_specs()):
        events.append(event)

    tr_event = next(e for e in events if e.type == "tool_result")
    assert tr_event.data == {"tool": "fail_tool", "result": {"error": "tool execution failed"}}, \
        f"tool_result failure payload must match old agent.py format, got: {tr_event.data}"


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
    """llm_error_streak >= 3 → yield error event and stop."""
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


class TestErrorStreakSemantics:
    """P0-4: dual error streak counters with per-turn semantics."""

    def test_agent_state_has_dual_counters(self):
        """AgentState should have llm_error_streak and tool_fail_streak."""
        state = AgentState(messages=[])
        assert hasattr(state, "llm_error_streak")
        assert hasattr(state, "tool_fail_streak")
        assert state.llm_error_streak == 0
        assert state.tool_fail_streak == 0

    def test_no_legacy_error_count(self):
        """Legacy error_count should not exist."""
        state = AgentState(messages=[])
        assert not hasattr(state, "error_count")


class TestLoopDetection:
    """P2-3: detect and skip duplicate tool calls."""

    def test_canonicalize_sorts_keys(self):
        from edu_cloud.ai.agent_loop import _canonicalize
        assert _canonicalize({"b": 1, "a": 2}) == {"a": 2, "b": 1}

    def test_canonicalize_nested(self):
        from edu_cloud.ai.agent_loop import _canonicalize
        result = _canonicalize({"z": {"b": 1, "a": 2}})
        assert list(result["z"].keys()) == ["a", "b"]

    def test_fingerprint_stable(self):
        from edu_cloud.ai.agent_loop import _canonicalize
        a = json.dumps(_canonicalize({"exam_id": "e1", "class_id": "c1"}), ensure_ascii=False, sort_keys=True)
        b = json.dumps(_canonicalize({"class_id": "c1", "exam_id": "e1"}), ensure_ascii=False, sort_keys=True)
        assert a == b

    def test_canonicalize_list(self):
        from edu_cloud.ai.agent_loop import _canonicalize
        result = _canonicalize([{"b": 1, "a": 2}])
        assert list(result[0].keys()) == ["a", "b"]


class TestLoopDetectionBehavior:
    """P2-3: behavioral tests through AgentLoop.run() entry — NOT logic mirrors.

    Gate 1 residual: GPT R3 required behavior-level tests via real AgentLoop entry.
    ORC-003: 3 consecutive same failures → 3rd skipped; success breaks chain.
    ORC-004: must use consecutive detection, not historical total count.
    """

    @pytest.mark.asyncio
    async def test_consecutive_failures_trigger_skip(self):
        """3 consecutive identical failed calls → 3rd is skipped (emits skip event)."""
        reg = ToolRegistry()
        exec_count = 0

        @reg.register(name="broken_tool", description="Always fails",
                      parameters={"exam_id": {"type": "string"}},
                      is_read_only=True, sensitivity="school")
        async def broken_tool(input: dict, ctx: ToolContext) -> ToolResult:
            nonlocal exec_count
            exec_count += 1
            return ToolResult(success=False, error="not found")

        ctx = ToolContext(db=None, school_id="S1", user_id="U1", role="admin")
        adapter = LLMProxyAdapter(base_url="http://test:8100", slot="primary")

        call_count = 0
        async def mock_chat(request):
            nonlocal call_count
            call_count += 1
            if call_count <= 3:
                # LLM keeps calling same broken tool with same args
                return LLMResponse(
                    tool_calls=[ToolCall(id=f"tc{call_count}", name="broken_tool",
                                        arguments={"exam_id": "E1"}, _raw={})],
                    usage=TokenUsage(10, 5), stop_reason="tool_use",
                )
            return LLMResponse(content="done", usage=TokenUsage(10, 5), stop_reason="end_turn")

        adapter.chat = mock_chat

        loop = AgentLoop(registry=reg, adapter=adapter, strategy=LoopStrategy.for_tier(3))
        events = []
        async for event in loop.run("test", ctx, tool_specs=reg.get_all_specs()):
            events.append(event)

        # Tool was actually executed only 2 times (3rd was skipped)
        assert exec_count == 2, f"Expected 2 actual executions (3rd skipped), got {exec_count}"

        # The skip produces a tool_result with "skipped: duplicate tool call"
        skip_events = [e for e in events if e.type == "tool_result"
                       and isinstance(e.data, dict)
                       and isinstance(e.data.get("result"), dict)
                       and "skipped" in str(e.data["result"].get("error", ""))]
        assert len(skip_events) >= 1, "Expected at least 1 skip event"

    @pytest.mark.asyncio
    async def test_success_breaks_consecutive_chain(self):
        """fail → success → fail → fail: success resets chain, no skip on 2nd failure pair."""
        reg = ToolRegistry()
        exec_count = 0

        call_sequence_results = [False, True, False, False]  # fail, success, fail, fail

        @reg.register(name="flaky_tool", description="Sometimes fails",
                      parameters={"exam_id": {"type": "string"}},
                      is_read_only=True, sensitivity="school")
        async def flaky_tool(input: dict, ctx: ToolContext) -> ToolResult:
            nonlocal exec_count
            idx = exec_count
            exec_count += 1
            if idx < len(call_sequence_results) and call_sequence_results[idx]:
                return ToolResult(success=True, data={"score": 85})
            return ToolResult(success=False, error="not found")

        ctx = ToolContext(db=None, school_id="S1", user_id="U1", role="admin")
        adapter = LLMProxyAdapter(base_url="http://test:8100", slot="primary")

        call_count = 0
        async def mock_chat(request):
            nonlocal call_count
            call_count += 1
            if call_count <= 4:
                return LLMResponse(
                    tool_calls=[ToolCall(id=f"tc{call_count}", name="flaky_tool",
                                        arguments={"exam_id": "E1"}, _raw={})],
                    usage=TokenUsage(10, 5), stop_reason="tool_use",
                )
            return LLMResponse(content="done", usage=TokenUsage(10, 5), stop_reason="end_turn")

        adapter.chat = mock_chat

        loop = AgentLoop(registry=reg, adapter=adapter, strategy=LoopStrategy.for_tier(3))
        events = []
        async for event in loop.run("test", ctx, tool_specs=reg.get_all_specs()):
            events.append(event)

        # All 4 calls should execute — success at position 1 breaks the chain
        assert exec_count == 4, f"Expected all 4 calls executed (success broke chain), got {exec_count}"

        # No skip events
        skip_events = [e for e in events if e.type == "tool_result"
                       and isinstance(e.data, dict)
                       and isinstance(e.data.get("result"), dict)
                       and "skipped" in str(e.data["result"].get("error", ""))]
        assert len(skip_events) == 0, "No calls should be skipped — success broke the chain"

    @pytest.mark.asyncio
    async def test_different_error_text_breaks_chain(self):
        """Different error texts should break the consecutive chain — no skip."""
        reg = ToolRegistry()
        exec_count = 0
        error_texts = ["not found", "timeout", "not found"]

        @reg.register(name="multi_error_tool", description="Fails with varying errors",
                      parameters={"exam_id": {"type": "string"}},
                      is_read_only=True, sensitivity="school")
        async def multi_error_tool(input: dict, ctx: ToolContext) -> ToolResult:
            nonlocal exec_count
            idx = exec_count
            exec_count += 1
            err = error_texts[idx] if idx < len(error_texts) else "unknown"
            return ToolResult(success=False, error=err)

        ctx = ToolContext(db=None, school_id="S1", user_id="U1", role="admin")
        adapter = LLMProxyAdapter(base_url="http://test:8100", slot="primary")

        call_count = 0
        async def mock_chat(request):
            nonlocal call_count
            call_count += 1
            if call_count <= 3:
                return LLMResponse(
                    tool_calls=[ToolCall(id=f"tc{call_count}", name="multi_error_tool",
                                        arguments={"exam_id": "E1"}, _raw={})],
                    usage=TokenUsage(10, 5), stop_reason="tool_use",
                )
            return LLMResponse(content="done", usage=TokenUsage(10, 5), stop_reason="end_turn")

        adapter.chat = mock_chat

        loop = AgentLoop(registry=reg, adapter=adapter, strategy=LoopStrategy.for_tier(3))
        events = []
        async for event in loop.run("test", ctx, tool_specs=reg.get_all_specs()):
            events.append(event)

        # All 3 calls should execute — "timeout" at position 1 breaks error-text chain
        assert exec_count == 3, f"Expected all 3 calls executed (different error broke chain), got {exec_count}"


class TestMultiToolPartialFailure:
    """F004/ORC-002: single turn with multiple tools, partial failure must NOT increment tool_fail_streak."""

    @pytest.mark.asyncio
    async def test_partial_failure_does_not_increment_streak(self):
        """LLM calls 2 tools in one turn: 1 succeeds, 1 fails → tool_fail_streak stays 0."""
        reg = ToolRegistry()

        @reg.register(name="good_tool", description="Always succeeds",
                      parameters={"x": {"type": "string"}},
                      is_read_only=True, sensitivity="school")
        async def good_tool(input: dict, ctx: ToolContext) -> ToolResult:
            return ToolResult(success=True, data={"ok": True})

        @reg.register(name="bad_tool", description="Always fails",
                      parameters={"x": {"type": "string"}},
                      is_read_only=True, sensitivity="school")
        async def bad_tool(input: dict, ctx: ToolContext) -> ToolResult:
            return ToolResult(success=False, error="broken")

        ctx = ToolContext(db=None, school_id="S1", user_id="U1", role="admin")
        adapter = LLMProxyAdapter(base_url="http://test:8100", slot="primary")

        call_count = 0
        async def mock_chat(request):
            nonlocal call_count
            call_count += 1
            if call_count <= 3:
                # Each turn sends 2 tools: 1 good + 1 bad (partial failure)
                return LLMResponse(
                    tool_calls=[
                        ToolCall(id=f"tc{call_count}a", name="good_tool", arguments={"x": "1"}, _raw={}),
                        ToolCall(id=f"tc{call_count}b", name="bad_tool", arguments={"x": "1"}, _raw={}),
                    ],
                    usage=TokenUsage(10, 5), stop_reason="tool_use",
                )
            return LLMResponse(content="done", usage=TokenUsage(10, 5), stop_reason="end_turn")

        adapter.chat = mock_chat

        loop = AgentLoop(registry=reg, adapter=adapter, strategy=LoopStrategy.for_tier(3))
        events = []
        async for event in loop.run("test", ctx, tool_specs=reg.get_all_specs()):
            events.append(event)

        types = [e.type for e in events]
        # Should NOT hit error threshold — partial failure doesn't count
        assert "error" not in types, "Partial failure should NOT trigger error event"
        assert "answer" in types, "Should reach answer after 3 turns of partial failure"
