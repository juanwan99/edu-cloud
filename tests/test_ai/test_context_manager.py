import pytest
from unittest.mock import AsyncMock
from edu_cloud.ai.context_manager import ContextManager, TokenCounter
from edu_cloud.ai.llm_adapter import LLMProxyAdapter, LLMResponse, TokenUsage
from edu_cloud.ai.schemas import Message


def test_token_counter_chinese():
    count = TokenCounter.estimate("你好世界")
    assert count == 6  # 4 chars * 1.5 = 6


def test_token_counter_english():
    count = TokenCounter.estimate("hello world")
    assert count == 4  # 11 chars * 0.4 ≈ 4


def test_token_counter_mixed():
    count = TokenCounter.estimate("你好 world")
    assert count > 0


def test_token_counter_messages():
    msgs = [
        Message(role="system", content="你是助手"),
        Message(role="user", content="hello"),
    ]
    count = TokenCounter.estimate_messages(msgs)
    assert count > 0


def test_should_compact_false():
    cm = ContextManager()
    assert cm.should_compact(token_count=5000, context_window=128_000) is False


def test_should_compact_true():
    cm = ContextManager()
    assert cm.should_compact(token_count=96_000, context_window=128_000) is True


@pytest.mark.asyncio
async def test_compact_preserves_system_and_recent():
    adapter = LLMProxyAdapter(base_url="http://test:8100", slot="primary")
    adapter.chat = AsyncMock(return_value=LLMResponse(
        content="Summary: user asked about exams, key finding is avg=85",
        usage=TokenUsage(100, 50),
    ))

    messages = [
        Message(role="system", content="You are an assistant"),
        Message(role="user", content="old question 1"),
        Message(role="assistant", content="old answer 1"),
        Message(role="user", content="old question 2"),
        Message(role="assistant", content="old answer 2"),
        Message(role="user", content="old question 3"),
        Message(role="assistant", content="old answer 3"),
        Message(role="user", content="recent question 1"),
        Message(role="assistant", content="recent answer 1"),
        Message(role="user", content="recent question 2"),
        Message(role="assistant", content="recent answer 2"),
    ]

    cm = ContextManager()
    new_messages = await cm.compact(messages, adapter)

    assert new_messages[0].role == "system"
    assert new_messages[0].content == "You are an assistant"
    assert "Summary" in new_messages[1].content
    assert new_messages[-1].content == "recent answer 2"
    assert len(new_messages) < len(messages)


@pytest.mark.asyncio
async def test_compact_with_tool_messages():
    """F001: compact correctly preserves turns when tool_calls/tool messages are present."""
    from edu_cloud.ai.schemas import ToolCall
    adapter = LLMProxyAdapter(base_url="http://test:8100", slot="primary")
    adapter.chat = AsyncMock(return_value=LLMResponse(
        content="Summary of old conversation",
        usage=TokenUsage(100, 50),
    ))

    messages = [
        Message(role="system", content="You are an assistant"),
        # Old turns
        Message(role="user", content="old q1"),
        Message(role="assistant", content="old a1"),
        Message(role="user", content="old q2"),
        Message(role="assistant", content=None, tool_calls=[
            ToolCall(id="tc1", name="get_exam", arguments={}, _raw={})
        ]),
        Message(role="tool", content='{"result": "ok"}', tool_call_id="tc1", name="get_exam"),
        Message(role="assistant", content="old a2 with tool result"),
        # Recent turns (should be preserved)
        Message(role="user", content="recent q1"),
        Message(role="assistant", content=None, tool_calls=[
            ToolCall(id="tc2", name="get_stats", arguments={}, _raw={})
        ]),
        Message(role="tool", content='{"stats": "data"}', tool_call_id="tc2", name="get_stats"),
        Message(role="assistant", content="recent a1 with stats"),
        Message(role="user", content="recent q2"),
        Message(role="assistant", content="recent a2"),
        Message(role="user", content="recent q3"),
        Message(role="assistant", content="recent a3"),
        Message(role="user", content="recent q4"),
        Message(role="assistant", content="recent a4"),
    ]

    cm = ContextManager()
    new_messages = await cm.compact(messages, adapter)

    # System + summary + recent 4 user turns (with their tool messages)
    assert new_messages[0].role == "system"
    assert "Summary" in new_messages[1].content
    # All 4 recent user messages should be preserved
    user_msgs = [m for m in new_messages if m.role == "user"]
    assert len(user_msgs) == 4
    assert user_msgs[0].content == "recent q1"
    assert new_messages[-1].content == "recent a4"


@pytest.mark.asyncio
async def test_compact_fallback_on_llm_failure():
    """F005: LLM summarization failure should fallback, not raise."""
    adapter = LLMProxyAdapter(base_url="http://test:8100", slot="primary")
    adapter.chat = AsyncMock(side_effect=Exception("LLM down"))

    messages = [
        Message(role="system", content="You are an assistant"),
        Message(role="user", content="old q1"),
        Message(role="assistant", content="old a1"),
        Message(role="user", content="old q2"),
        Message(role="assistant", content="old a2"),
        Message(role="user", content="old q3"),
        Message(role="assistant", content="old a3"),
        Message(role="user", content="recent q1"),
        Message(role="assistant", content="recent a1"),
        Message(role="user", content="recent q2"),
        Message(role="assistant", content="recent a2"),
    ]

    cm = ContextManager()
    new_messages = await cm.compact(messages, adapter)

    assert new_messages[0].role == "system"
    assert "简略" in new_messages[1].content  # fallback summary
    assert new_messages[-1].content == "recent a2"
