import pytest
from unittest.mock import AsyncMock
from edu_cloud.ai.agent import Agent
from edu_cloud.ai.schemas import ChatMessage, ToolCall
from edu_cloud.ai.registry import ToolRegistry


@pytest.fixture
def test_registry():
    reg = ToolRegistry()

    @reg.register(
        name="mock_tool",
        description="返回固定数据",
        category="test",
        parameters={
            "type": "object",
            "properties": {"q": {"type": "string"}},
            "required": ["q"],
        },
    )
    async def _mock_tool(q: str, _db=None) -> dict:
        return {"answer": f"result for {q}"}

    return reg


@pytest.mark.asyncio
async def test_agent_direct_answer(test_registry):
    """LLM directly answers without tool calls"""
    mock_llm = AsyncMock()
    mock_llm.chat.return_value = ChatMessage(role="assistant", content="你好，我是 AI 助手")
    agent = Agent(llm=mock_llm, registry=test_registry)
    events = []
    async for event in agent.run(
        "你好",
        session_id="test",
        db=None,
        school_id=None,
        class_ids=None,
        role="principal",
        display_name="校长",
        scope={},
    ):
        events.append(event)
    assert any(e.type == "answer" for e in events)
    answer = next(e for e in events if e.type == "answer")
    assert "你好" in answer.data["content"]


@pytest.mark.asyncio
async def test_agent_tool_call(test_registry):
    """LLM calls tool then answers"""
    mock_llm = AsyncMock()
    mock_llm.chat.side_effect = [
        ChatMessage(
            role="assistant",
            content=None,
            tool_calls=[ToolCall(id="tc1", name="mock_tool", arguments={"q": "数学"})],
        ),
        ChatMessage(role="assistant", content="数学的结果是 result for 数学"),
    ]
    agent = Agent(llm=mock_llm, registry=test_registry)
    events = []
    async for event in agent.run(
        "查数学",
        session_id="test",
        db=None,
        school_id=None,
        class_ids=None,
        role="principal",
        display_name="校长",
        scope={},
    ):
        events.append(event)
    types = [e.type for e in events]
    assert "tool_call" in types
    assert "tool_result" in types
    assert "answer" in types


@pytest.mark.asyncio
async def test_agent_max_steps(test_registry):
    """Exceeds max_steps → forced stop"""
    mock_llm = AsyncMock()
    mock_llm.chat.return_value = ChatMessage(
        role="assistant",
        content=None,
        tool_calls=[ToolCall(id="tc1", name="mock_tool", arguments={"q": "loop"})],
    )
    agent = Agent(llm=mock_llm, registry=test_registry, max_steps=2)
    events = []
    async for event in agent.run(
        "无限循环",
        session_id="test",
        db=None,
        school_id=None,
        class_ids=None,
        role="principal",
        display_name="校长",
        scope={},
    ):
        events.append(event)
    assert any(e.type in ("answer", "error") for e in events)
    assert mock_llm.chat.call_count <= 3


@pytest.mark.asyncio
async def test_agent_unknown_role_no_tools(test_registry):
    """Unknown role gets no tool access"""
    mock_llm = AsyncMock()
    mock_llm.chat.return_value = ChatMessage(role="assistant", content="我无法访问工具")
    agent = Agent(llm=mock_llm, registry=test_registry)
    events = []
    async for event in agent.run(
        "查数据",
        session_id="test",
        db=None,
        school_id=None,
        class_ids=None,
        role="unknown_role",
        display_name="未知用户",
        scope={},
    ):
        events.append(event)
    # LLM should be called with no tools (unknown role → empty categories → no schemas)
    call_kwargs = mock_llm.chat.call_args
    assert call_kwargs is not None
    # tools arg should be None (empty list converted to None)
    tools_passed = call_kwargs[1].get("tools") if call_kwargs[1] else call_kwargs[0][1] if len(call_kwargs[0]) > 1 else None
    assert tools_passed is None


@pytest.mark.asyncio
async def test_agent_tool_error_continues(test_registry):
    """Tool execution error → error result injected into messages, LLM continues"""
    reg = ToolRegistry()

    @reg.register(
        name="failing_tool",
        description="总是失败",
        category="L1_analytics",
        parameters={"type": "object", "properties": {}, "required": []},
    )
    async def _failing_tool(_db=None) -> dict:
        raise RuntimeError("DB connection failed")

    mock_llm = AsyncMock()
    mock_llm.chat.side_effect = [
        ChatMessage(
            role="assistant",
            content=None,
            tool_calls=[ToolCall(id="tc1", name="failing_tool", arguments={})],
        ),
        ChatMessage(role="assistant", content="工具调用失败，我来解释一下"),
    ]
    agent = Agent(llm=mock_llm, registry=reg)
    events = []
    async for event in agent.run(
        "查数据",
        session_id="test",
        db=None,
        school_id=None,
        class_ids=None,
        role="principal",
        display_name="校长",
        scope={},
    ):
        events.append(event)
    types = [e.type for e in events]
    assert "tool_call" in types
    assert "tool_result" in types
    assert "answer" in types
    # tool_result should contain error info
    tool_result_event = next(e for e in events if e.type == "tool_result")
    assert "error" in tool_result_event.data["result"]


@pytest.mark.asyncio
async def test_agent_llm_error_yields_error_event(test_registry):
    """LLM raises exception → error event yielded"""
    mock_llm = AsyncMock()
    mock_llm.chat.side_effect = Exception("LLM service unavailable")
    agent = Agent(llm=mock_llm, registry=test_registry)
    events = []
    async for event in agent.run(
        "你好",
        session_id="test",
        db=None,
        school_id=None,
        class_ids=None,
        role="principal",
        display_name="校长",
        scope={},
    ):
        events.append(event)
    assert any(e.type == "error" for e in events)


@pytest.mark.asyncio
async def test_agent_calls_audit_log_tool_call(test_registry):
    """Agent calls audit.log_tool_call() after each tool execution."""
    mock_llm = AsyncMock()
    mock_llm.chat.side_effect = [
        ChatMessage(
            role="assistant",
            content=None,
            tool_calls=[ToolCall(id="tc1", name="mock_tool", arguments={"q": "测试"})],
        ),
        ChatMessage(role="assistant", content="完成"),
    ]
    mock_audit = AsyncMock()
    agent = Agent(llm=mock_llm, registry=test_registry)
    events = []
    async for event in agent.run(
        "查数据",
        session_id="test-session",
        db=None,
        school_id=None,
        class_ids=None,
        role="principal",
        display_name="校长",
        scope={"user_id": "u123"},
        audit=mock_audit,
    ):
        events.append(event)
    # audit.log_tool_call should have been called once
    mock_audit.log_tool_call.assert_called_once()
    call_kwargs = mock_audit.log_tool_call.call_args[1]
    assert call_kwargs["session_id"] == "test-session"
    assert call_kwargs["tool"] == "mock_tool"
    assert call_kwargs["role"] == "principal"
    assert call_kwargs["duration_ms"] >= 0


@pytest.mark.asyncio
async def test_agent_platform_admin_gets_all_tools():
    """platform_admin role gets access to all tool categories"""
    reg = ToolRegistry()

    @reg.register(name="tool_a", description="A", category="L1_analytics",
                  parameters={"type": "object", "properties": {}})
    async def _a() -> dict:
        return {}

    @reg.register(name="tool_b", description="B", category="L2_cross_school",
                  parameters={"type": "object", "properties": {}})
    async def _b() -> dict:
        return {}

    mock_llm = AsyncMock()
    mock_llm.chat.return_value = ChatMessage(role="assistant", content="完成")
    agent = Agent(llm=mock_llm, registry=reg)
    events = []
    async for event in agent.run(
        "查询",
        session_id="test",
        db=None,
        school_id=None,
        class_ids=None,
        role="platform_admin",
        display_name="管理员",
        scope={},
    ):
        events.append(event)
    # platform_admin → categories=None → all tools passed
    call_kwargs = mock_llm.chat.call_args
    tools_passed = call_kwargs[1].get("tools")
    assert tools_passed is not None
    tool_names = [t["function"]["name"] for t in tools_passed]
    assert "tool_a" in tool_names
    assert "tool_b" in tool_names
