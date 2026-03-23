"""Tests for LLMChatClient — OpenAI / Anthropic dual-protocol, retry, provider detection."""
import json
from unittest.mock import AsyncMock, patch, MagicMock

import httpx
import pytest

from edu_cloud.ai.llm import LLMChatClient
from edu_cloud.ai.schemas import ChatMessage, ToolCall


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

def _make_response(status_code: int, json_body: dict | None = None, text: str = ""):
    """Build a fake httpx.Response."""
    resp = MagicMock(spec=httpx.Response)
    resp.status_code = status_code
    resp.text = text or json.dumps(json_body or {})
    resp.json.return_value = json_body or {}
    return resp


def _openai_chat_response(content: str | None = None, tool_calls: list[dict] | None = None):
    """Standard OpenAI chat/completions JSON body."""
    msg: dict = {"role": "assistant"}
    if content is not None:
        msg["content"] = content
    if tool_calls is not None:
        msg["tool_calls"] = tool_calls
    return {"choices": [{"message": msg}]}


def _anthropic_response(content_blocks: list[dict]):
    """Standard Anthropic messages JSON body."""
    return {"content": content_blocks}


# ---------------------------------------------------------------------------
# 1. OpenAI path: successful chat with tool_calls response
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_openai_chat_with_tool_calls():
    """OpenAI path returns ChatMessage with parsed tool_calls."""
    tool_calls_raw = [
        {
            "id": "call_abc",
            "type": "function",
            "function": {
                "name": "get_weather",
                "arguments": '{"city": "Beijing"}',
            },
        }
    ]
    body = _openai_chat_response(content="Let me check.", tool_calls=tool_calls_raw)
    mock_resp = _make_response(200, body)

    client = LLMChatClient(
        api_url="https://api.openai.com/v1",
        api_key="sk-test",
        model="gpt-4",
    )
    try:
        with patch.object(client._http, "post", new_callable=AsyncMock, return_value=mock_resp):
            result = await client.chat([ChatMessage(role="user", content="weather?")])

        assert result.role == "assistant"
        assert result.content == "Let me check."
        assert result.tool_calls is not None
        assert len(result.tool_calls) == 1
        tc = result.tool_calls[0]
        assert tc.id == "call_abc"
        assert tc.name == "get_weather"
        assert tc.arguments == {"city": "Beijing"}
    finally:
        await client.close()


# ---------------------------------------------------------------------------
# 2. Anthropic path: successful chat with tool_use response
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_anthropic_chat_with_tool_use():
    """Anthropic path (URL contains 'anthropic') returns tool_calls from tool_use blocks."""
    body = _anthropic_response([
        {"type": "tool_use", "id": "toolu_01", "name": "search", "input": {"q": "test"}},
    ])
    mock_resp = _make_response(200, body)

    client = LLMChatClient(
        api_url="https://api.anthropic.com/v1/messages",
        api_key="sk-ant-test",
        model="claude-sonnet-4-20250514",
    )
    try:
        with patch.object(client._http, "post", new_callable=AsyncMock, return_value=mock_resp):
            result = await client.chat([ChatMessage(role="user", content="search something")])

        assert result.role == "assistant"
        assert result.content is None  # no text block
        assert result.tool_calls is not None
        assert len(result.tool_calls) == 1
        assert result.tool_calls[0].id == "toolu_01"
        assert result.tool_calls[0].name == "search"
        assert result.tool_calls[0].arguments == {"q": "test"}
    finally:
        await client.close()


# ---------------------------------------------------------------------------
# 3. Anthropic tool_result format: tool_call_id → tool_use_id mapping
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_anthropic_tool_result_id_mapping():
    """When sending a tool result, ChatMessage.tool_call_id maps to Anthropic tool_use_id."""
    body = _anthropic_response([{"type": "text", "text": "Done."}])
    mock_resp = _make_response(200, body)

    client = LLMChatClient(
        api_url="https://api.anthropic.com/v1/messages",
        api_key="sk-ant-test",
        model="claude-sonnet-4-20250514",
    )
    try:
        messages = [
            ChatMessage(role="user", content="Use the tool"),
            ChatMessage(
                role="assistant",
                content=None,
                tool_calls=[ToolCall(id="toolu_99", name="calc", arguments={"x": 1})],
            ),
            ChatMessage(role="tool", content="42", tool_call_id="toolu_99", name="calc"),
        ]

        captured_payload = {}

        async def capture_post(url, json, headers):
            captured_payload.update(json)
            return mock_resp

        with patch.object(client._http, "post", side_effect=capture_post):
            await client.chat(messages)

        # Verify the tool result message uses tool_use_id (Anthropic format)
        conv = captured_payload["messages"]
        # The tool result should be the last user message with content blocks
        tool_result_msg = conv[-1]
        assert tool_result_msg["role"] == "user"
        assert len(tool_result_msg["content"]) == 1
        block = tool_result_msg["content"][0]
        assert block["type"] == "tool_result"
        assert block["tool_use_id"] == "toolu_99"
        assert block["content"] == "42"
    finally:
        await client.close()


# ---------------------------------------------------------------------------
# 4. Mixed content + tool_use Anthropic response
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_anthropic_mixed_text_and_tool_use():
    """Anthropic response with both text and tool_use blocks parses correctly."""
    body = _anthropic_response([
        {"type": "text", "text": "I'll search for that."},
        {"type": "tool_use", "id": "toolu_mix", "name": "web_search", "input": {"query": "hello"}},
        {"type": "text", "text": "And also check this."},
    ])
    mock_resp = _make_response(200, body)

    client = LLMChatClient(
        api_url="https://api.anthropic.com/v1/messages",
        api_key="sk-ant-test",
        model="claude-sonnet-4-20250514",
    )
    try:
        with patch.object(client._http, "post", new_callable=AsyncMock, return_value=mock_resp):
            result = await client.chat([ChatMessage(role="user", content="find info")])

        # text parts joined with newline
        assert result.content == "I'll search for that.\nAnd also check this."
        assert result.tool_calls is not None
        assert len(result.tool_calls) == 1
        assert result.tool_calls[0].id == "toolu_mix"
        assert result.tool_calls[0].name == "web_search"
        assert result.tool_calls[0].arguments == {"query": "hello"}
    finally:
        await client.close()


# ---------------------------------------------------------------------------
# 5. Retry on non-200 response (verify 3 attempts)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_openai_retries_on_non_200():
    """Non-200 responses trigger retries; success on 3rd attempt returns normally."""
    fail_resp = _make_response(500, text="Internal Server Error")
    success_body = _openai_chat_response(content="ok")
    success_resp = _make_response(200, success_body)

    client = LLMChatClient(
        api_url="https://api.openai.com/v1",
        api_key="sk-test",
        model="gpt-4",
        max_retries=3,
    )
    try:
        mock_post = AsyncMock(side_effect=[fail_resp, fail_resp, success_resp])
        with patch.object(client._http, "post", mock_post):
            result = await client.chat([ChatMessage(role="user", content="hi")])

        assert result.content == "ok"
        assert mock_post.call_count == 3
    finally:
        await client.close()


# ---------------------------------------------------------------------------
# 6. Final failure after max retries raises RuntimeError
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_openai_raises_after_max_retries():
    """All retries exhausted → RuntimeError."""
    fail_resp = _make_response(502, text="Bad Gateway")

    client = LLMChatClient(
        api_url="https://api.openai.com/v1",
        api_key="sk-test",
        model="gpt-4",
        max_retries=3,
    )
    try:
        mock_post = AsyncMock(return_value=fail_resp)
        with patch.object(client._http, "post", mock_post):
            with pytest.raises(RuntimeError, match="LLM chat failed after 3 attempts"):
                await client.chat([ChatMessage(role="user", content="fail")])

        assert mock_post.call_count == 3
    finally:
        await client.close()


@pytest.mark.asyncio
async def test_anthropic_raises_after_max_retries():
    """Anthropic path: all retries exhausted → RuntimeError."""
    fail_resp = _make_response(429, text="Rate limited")

    client = LLMChatClient(
        api_url="https://api.anthropic.com/v1/messages",
        api_key="sk-ant-test",
        model="claude-sonnet-4-20250514",
        max_retries=2,
    )
    try:
        mock_post = AsyncMock(return_value=fail_resp)
        with patch.object(client._http, "post", mock_post):
            with pytest.raises(RuntimeError, match="LLM anthropic failed after 2 attempts"):
                await client.chat([ChatMessage(role="user", content="fail")])

        assert mock_post.call_count == 2
    finally:
        await client.close()


# ---------------------------------------------------------------------------
# 7. Provider auto-detection (proxy mode uses OpenAI even with anthropic in URL)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_proxy_mode_uses_openai_format():
    """When slot is set (proxy mode), always use OpenAI format even if URL contains 'anthropic'."""
    body = _openai_chat_response(content="proxy ok")
    mock_resp = _make_response(200, body)

    client = LLMChatClient(
        api_url="https://my-proxy.com/anthropic-compatible",
        api_key="",
        model="claude-sonnet-4-20250514",
        slot="slot-1",
    )
    try:
        assert client._is_proxy is True
        assert client._is_anthropic is False  # proxy overrides anthropic detection

        captured_url = None

        async def capture_post(url, **kwargs):
            nonlocal captured_url
            captured_url = url
            return mock_resp

        with patch.object(client._http, "post", side_effect=capture_post):
            result = await client.chat([ChatMessage(role="user", content="test")])

        assert result.content == "proxy ok"
        # OpenAI path appends /chat/completions
        assert captured_url.endswith("/chat/completions")
    finally:
        await client.close()


@pytest.mark.asyncio
async def test_no_slot_anthropic_detected():
    """Without slot, URL containing 'anthropic' triggers Anthropic path."""
    client = LLMChatClient(
        api_url="https://api.anthropic.com/v1/messages",
        api_key="sk-ant-test",
        model="claude-sonnet-4-20250514",
    )
    try:
        assert client._is_proxy is False
        assert client._is_anthropic is True
    finally:
        await client.close()


@pytest.mark.asyncio
async def test_no_slot_openai_detected():
    """Without slot, URL without 'anthropic' triggers OpenAI path."""
    client = LLMChatClient(
        api_url="https://api.openai.com/v1",
        api_key="sk-test",
        model="gpt-4",
    )
    try:
        assert client._is_proxy is False
        assert client._is_anthropic is False
    finally:
        await client.close()


# ---------------------------------------------------------------------------
# Additional edge cases
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_openai_sends_correct_headers_with_api_key():
    """OpenAI (non-proxy) path sends Authorization Bearer header."""
    body = _openai_chat_response(content="hi")
    mock_resp = _make_response(200, body)

    client = LLMChatClient(
        api_url="https://api.openai.com/v1",
        api_key="sk-secret",
        model="gpt-4",
    )
    try:
        captured_headers = {}

        async def capture_post(url, json, headers):
            captured_headers.update(headers)
            return mock_resp

        with patch.object(client._http, "post", side_effect=capture_post):
            await client.chat([ChatMessage(role="user", content="hi")])

        assert captured_headers["Authorization"] == "Bearer sk-secret"
        assert "X-LLM-Slot" not in captured_headers
    finally:
        await client.close()


@pytest.mark.asyncio
async def test_proxy_sends_slot_header():
    """Proxy mode sends X-LLM-Slot header instead of Authorization."""
    body = _openai_chat_response(content="ok")
    mock_resp = _make_response(200, body)

    client = LLMChatClient(
        api_url="https://proxy.example.com",
        api_key="ignored",
        model="gpt-4",
        slot="my-slot",
    )
    try:
        captured_headers = {}

        async def capture_post(url, json, headers):
            captured_headers.update(headers)
            return mock_resp

        with patch.object(client._http, "post", side_effect=capture_post):
            await client.chat([ChatMessage(role="user", content="hi")])

        assert captured_headers["X-LLM-Slot"] == "my-slot"
        assert "Authorization" not in captured_headers
    finally:
        await client.close()


@pytest.mark.asyncio
async def test_anthropic_system_message_extraction():
    """Anthropic path extracts system messages into top-level 'system' field."""
    body = _anthropic_response([{"type": "text", "text": "Hello!"}])
    mock_resp = _make_response(200, body)

    client = LLMChatClient(
        api_url="https://api.anthropic.com/v1/messages",
        api_key="sk-ant-test",
        model="claude-sonnet-4-20250514",
    )
    try:
        captured_payload = {}

        async def capture_post(url, json, headers):
            captured_payload.update(json)
            return mock_resp

        messages = [
            ChatMessage(role="system", content="You are helpful."),
            ChatMessage(role="user", content="Hi"),
        ]
        with patch.object(client._http, "post", side_effect=capture_post):
            await client.chat(messages)

        # system should be a top-level field, not in messages
        assert captured_payload["system"] == "You are helpful."
        # messages should only have the user message
        assert len(captured_payload["messages"]) == 1
        assert captured_payload["messages"][0]["role"] == "user"
    finally:
        await client.close()


@pytest.mark.asyncio
async def test_openai_retries_on_network_error():
    """Network errors (TimeoutException) trigger retries."""
    body = _openai_chat_response(content="recovered")
    success_resp = _make_response(200, body)

    client = LLMChatClient(
        api_url="https://api.openai.com/v1",
        api_key="sk-test",
        model="gpt-4",
        max_retries=3,
    )
    try:
        mock_post = AsyncMock(side_effect=[
            httpx.TimeoutException("timed out"),
            httpx.ConnectError("connection refused"),
            success_resp,
        ])
        with patch.object(client._http, "post", mock_post):
            result = await client.chat([ChatMessage(role="user", content="retry me")])

        assert result.content == "recovered"
        assert mock_post.call_count == 3
    finally:
        await client.close()
