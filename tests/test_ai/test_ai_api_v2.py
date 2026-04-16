"""SSE event contract tests — serialization + integration + backward compat (Task 14)."""
import json
import pytest
from unittest.mock import AsyncMock
from edu_cloud.ai.schemas import AgentEvent
from edu_cloud.ai.agent_loop import AgentLoop
from edu_cloud.ai.llm_adapter import LLMProxyAdapter, LLMResponse, TokenUsage
from edu_cloud.ai.registry import ToolRegistry
from edu_cloud.ai.tool_context import ToolContext, ToolResult
from edu_cloud.ai.capability_probe import LoopStrategy
from edu_cloud.ai.schemas import ToolCall


def test_agent_event_serialization_for_sse():
    """Verify all new event types serialize correctly for SSE."""
    events = [
        AgentEvent(type="thinking", data={"content": "分析中..."}),
        AgentEvent(type="plan", data={"tasks": [{"id": "0", "description": "收集数据"}]}),
        AgentEvent(type="task_update", data={"id": "0", "status": "in_progress"}),
        AgentEvent(type="tool_call", data={"tool": "get_exam", "args": {}}),
        AgentEvent(type="tool_result", data={"tool": "get_exam", "success": True, "data": {}}),
        AgentEvent(type="answer", data={"content": "分析结果..."}),
        AgentEvent(type="done", data={"turns": 3, "tokens": 5000}),
    ]
    for event in events:
        d = event.to_dict()
        assert "type" in d
        assert "data" in d
        line = f"data: {json.dumps(d, ensure_ascii=False)}\n\n"
        assert event.type in line


def test_sse_event_backward_compat():
    """INV-004: old event types (answer/tool_call/tool_result/done) format unchanged."""
    # answer: must have {"type": "answer", "data": {"content": ...}}
    answer = AgentEvent(type="answer", data={"content": "回答"})
    d = answer.to_dict()
    assert d == {"type": "answer", "data": {"content": "回答"}}

    # tool_call: exact old agent.py format — only "tool" + "arguments", no extra keys
    tool_call = AgentEvent(type="tool_call", data={"tool": "get_score", "arguments": {"exam_id": "E1"}})
    d = tool_call.to_dict()
    assert d == {"type": "tool_call", "data": {"tool": "get_score", "arguments": {"exam_id": "E1"}}}, \
        f"INV-004: tool_call exact format mismatch: {d}"

    # tool_result: exact old agent.py format — only "tool" + "result" (raw dict, not ToolResult wrapper)
    tool_result = AgentEvent(type="tool_result", data={"tool": "get_score", "result": {"avg": 85.2}})
    d = tool_result.to_dict()
    assert d == {"type": "tool_result", "data": {"tool": "get_score", "result": {"avg": 85.2}}}, \
        f"INV-004: tool_result exact format mismatch: {d}"

    # done: exact payload
    done = AgentEvent(type="done", data={"turns": 5, "tokens": 3000})
    d = done.to_dict()
    assert d == {"type": "done", "data": {"turns": 5, "tokens": 3000}}, \
        f"done exact format mismatch: {d}"

    # tool_result failure: must emit {"tool": ..., "result": {"error": ...}} matching old agent.py
    tool_result_fail = AgentEvent(type="tool_result", data={"tool": "get_score", "result": {"error": "not found"}})
    d = tool_result_fail.to_dict()
    assert d == {"type": "tool_result", "data": {"tool": "get_score", "result": {"error": "not found"}}}, \
        f"INV-004: tool_result failure format mismatch: {d}"


@pytest.mark.asyncio
async def test_agentloop_produces_valid_sse_event_stream():
    """Integration: AgentLoop → collect events → simulate SSE serialization."""
    reg = ToolRegistry()

    @reg.register(name="get_score", description="Get score", parameters={"exam_id": {"type": "string"}},
                  is_read_only=True, sensitivity="school")
    async def get_score(input: dict, ctx: ToolContext) -> ToolResult:
        return ToolResult(success=True, data={"avg": 85.2})

    ctx = ToolContext(db=None, school_id="S1", user_id="U1", role="teacher")
    adapter = LLMProxyAdapter(base_url="http://test:8100", slot="primary")

    call_count = 0
    async def mock_chat(request):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            return LLMResponse(
                tool_calls=[ToolCall(id="tc1", name="get_score", arguments={"exam_id": "E1"}, _raw={})],
                usage=TokenUsage(20, 10), stop_reason="tool_use",
            )
        return LLMResponse(content="平均分 85.2", usage=TokenUsage(20, 10), stop_reason="end_turn")

    adapter.chat = mock_chat

    loop = AgentLoop(registry=reg, adapter=adapter, strategy=LoopStrategy.for_tier(3))
    sse_lines = []
    async for event in loop.run("查成绩", ctx, tool_specs=reg.get_all_specs()):
        d = event.to_dict()
        line = f"data: {json.dumps(d, ensure_ascii=False)}\n\n"
        sse_lines.append(line)
        # Verify each line is valid SSE format
        assert line.startswith("data: ")
        assert line.endswith("\n\n")
        parsed = json.loads(line[6:].strip())
        assert "type" in parsed
        assert "data" in parsed

    # Verify event stream contains expected types
    types = [json.loads(line[6:].strip())["type"] for line in sse_lines]
    assert "tool_call" in types
    assert "tool_result" in types
    assert "answer" in types
    assert "done" in types

    # INV-004: verify exact backward-compatible payload in actual stream
    tc_line = next(l for l in sse_lines if '"tool_call"' in l)
    tc_data = json.loads(tc_line[6:].strip())["data"]
    assert tc_data == {"tool": "get_score", "arguments": {"exam_id": "E1"}}, \
        f"INV-004: tool_call stream payload mismatch: {tc_data}"

    tr_line = next(l for l in sse_lines if '"tool_result"' in l)
    tr_data = json.loads(tr_line[6:].strip())["data"]
    assert tr_data == {"tool": "get_score", "result": {"avg": 85.2}}, \
        f"INV-004: tool_result stream payload mismatch: {tr_data}"


@pytest.mark.asyncio
async def test_agentloop_anonymizer_integration():
    """F003: tool results are anonymized in messages, answer is deanonymized."""
    from edu_cloud.ai.anonymizer import Anonymizer

    reg = ToolRegistry()

    @reg.register(name="get_roster", description="Get roster", parameters={},
                  is_read_only=True, sensitivity="student")
    async def get_roster(input: dict, ctx: ToolContext) -> ToolResult:
        return ToolResult(success=True, data={
            "students": [{"student_name": "张三", "student_number": "T001", "id": "s1"}]
        })

    anonymizer = Anonymizer()
    ctx = ToolContext(db=None, school_id="S1", user_id="U1", role="teacher", anonymizer=anonymizer)
    adapter = LLMProxyAdapter(base_url="http://test:8100", slot="primary")

    call_count = 0
    captured_messages_round2 = None

    async def mock_chat(request):
        nonlocal call_count, captured_messages_round2
        call_count += 1
        if call_count == 1:
            return LLMResponse(
                tool_calls=[ToolCall(id="tc1", name="get_roster", arguments={}, _raw={})],
                usage=TokenUsage(20, 10), stop_reason="tool_use",
            )
        # Capture messages sent to LLM on round 2 (after tool execution)
        captured_messages_round2 = request.messages
        # LLM sees anonymized code S001, uses it in answer
        return LLMResponse(content="S001 的成绩很好", usage=TokenUsage(20, 10), stop_reason="end_turn")

    adapter.chat = mock_chat

    loop = AgentLoop(registry=reg, adapter=adapter, strategy=LoopStrategy.for_tier(3))
    events = []
    async for event in loop.run("查名单", ctx, tool_specs=reg.get_all_specs()):
        events.append(event)

    # tool_result SSE event should have original (non-anonymized) data for frontend
    tr_evt = next(e for e in events if e.type == "tool_result")
    assert tr_evt.data["result"]["students"][0]["student_name"] == "张三"

    # NEW-F006: verify messages sent to LLM contain anonymized data (not real names)
    assert captured_messages_round2 is not None, "Round 2 messages not captured"
    tool_msg = next(m for m in captured_messages_round2 if m.role == "tool")
    assert "S001" in tool_msg.content, \
        f"NEW-F006: tool message to LLM should contain anonymized code S001, got: {tool_msg.content}"
    assert "张三" not in tool_msg.content, \
        f"NEW-F006: tool message to LLM should NOT contain real name 张三, got: {tool_msg.content}"
    # student_number should be stripped entirely
    assert "T001" not in tool_msg.content, \
        f"NEW-F006: tool message should NOT contain student_number T001, got: {tool_msg.content}"

    # answer event should have deanonymized text (codes → real names)
    answer_evt = next(e for e in events if e.type == "answer")
    assert "张三" in answer_evt.data["content"], \
        f"F003: answer should be deanonymized, got: {answer_evt.data['content']}"
    assert "S001" not in answer_evt.data["content"]
