import json
import pytest
import httpx
from unittest.mock import AsyncMock, patch
from edu_cloud.ai.llm_adapter import LLMProxyAdapter, LLMRequest, LLMResponse, TokenUsage
from edu_cloud.ai.schemas import Message, ToolCall


def _mock_response(status_code, json_data):
    """Create httpx.Response with a request so raise_for_status() works."""
    return httpx.Response(
        status_code,
        json=json_data,
        request=httpx.Request("POST", "http://test/v1/chat/completions"),
    )


def test_llm_request_defaults():
    req = LLMRequest(messages=[Message(role="user", content="hi")])
    assert req.temperature == 0.7
    assert req.max_tokens == 4096
    assert req.stream is True
    assert req.tools is None


def test_llm_response_fields():
    resp = LLMResponse(
        content="hello",
        tool_calls=None,
        usage=TokenUsage(input_tokens=10, output_tokens=5),
        stop_reason="end_turn",
    )
    assert resp.content == "hello"
    assert resp.usage.total == 15


@pytest.mark.asyncio
async def test_proxy_adapter_chat_basic():
    adapter = LLMProxyAdapter(base_url="http://localhost:8100", slot="primary")

    mock_response = _mock_response(200, {
        "choices": [{"message": {"role": "assistant", "content": "hi"}, "finish_reason": "stop"}],
        "usage": {"prompt_tokens": 10, "completion_tokens": 5},
    })
    with patch.object(adapter._http, "post", new_callable=AsyncMock, return_value=mock_response):
        resp = await adapter.chat(LLMRequest(
            messages=[Message(role="user", content="hello")],
            stream=False,
        ))
    assert resp.content == "hi"
    assert resp.stop_reason == "end_turn"
    assert resp.usage.input_tokens == 10


@pytest.mark.asyncio
async def test_proxy_adapter_chat_with_tool_calls():
    adapter = LLMProxyAdapter(base_url="http://localhost:8100", slot="primary")

    mock_response = _mock_response(200, {
        "choices": [{
            "message": {
                "role": "assistant",
                "content": None,
                "tool_calls": [{
                    "id": "tc1",
                    "type": "function",
                    "function": {"name": "get_exam", "arguments": json.dumps({"exam_id": "E1"})},
                }],
            },
            "finish_reason": "tool_calls",
        }],
        "usage": {"prompt_tokens": 20, "completion_tokens": 10},
    })
    with patch.object(adapter._http, "post", new_callable=AsyncMock, return_value=mock_response):
        resp = await adapter.chat(LLMRequest(
            messages=[Message(role="user", content="show exam")],
            tools=[{"type": "function", "function": {"name": "get_exam", "parameters": {}}}],
            stream=False,
        ))
    assert resp.content is None
    assert len(resp.tool_calls) == 1
    assert resp.tool_calls[0].name == "get_exam"
    assert resp.tool_calls[0].arguments == {"exam_id": "E1"}  # F004: assert parsed arguments
    assert resp.stop_reason == "tool_use"


# -- F004: plan boundary condition tests --


def test_parse_response_empty_choices():
    """F002+F004: choices=[] should not raise, returns empty LLMResponse."""
    from edu_cloud.ai.llm_adapter import LLMProxyAdapter
    resp = LLMProxyAdapter._parse_response({"choices": [], "usage": {}})
    assert resp.content is None
    assert resp.tool_calls is None
    assert resp.usage.input_tokens == 0


def test_parse_response_missing_usage():
    """F004: missing usage field defaults to TokenUsage(0, 0)."""
    from edu_cloud.ai.llm_adapter import LLMProxyAdapter
    resp = LLMProxyAdapter._parse_response({
        "choices": [{"message": {"role": "assistant", "content": "ok"}, "finish_reason": "stop"}],
    })
    assert resp.content == "ok"
    assert resp.usage.input_tokens == 0
    assert resp.usage.output_tokens == 0


def test_parse_response_function_call_finish_reason():
    """F004: legacy 'function_call' finish_reason maps to 'tool_use'."""
    from edu_cloud.ai.llm_adapter import LLMProxyAdapter
    resp = LLMProxyAdapter._parse_response({
        "choices": [{"message": {"role": "assistant", "content": "hi"}, "finish_reason": "function_call"}],
        "usage": {},
    })
    assert resp.stop_reason == "tool_use"


class TestLLMRetry:
    """P1-1: graded retry for LLM calls."""

    @pytest.mark.asyncio
    async def test_429_retries_up_to_3_times(self):
        """429 Too Many Requests should retry up to 3 times."""
        adapter = LLMProxyAdapter(base_url="http://fake:8100", slot="test")
        call_count = 0

        async def mock_post(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            resp = _mock_response(429, {})
            resp.headers = {}
            return resp

        adapter._http = AsyncMock()
        adapter._http.post = mock_post

        with pytest.raises(httpx.HTTPStatusError):
            await adapter.chat(LLMRequest(
                messages=[Message(role="user", content="test")],
            ))

        assert call_count == 4  # 1 initial + 3 retries

    @pytest.mark.asyncio
    async def test_500_retries_once(self):
        """500 should retry exactly once."""
        adapter = LLMProxyAdapter(base_url="http://fake:8100", slot="test")
        call_count = 0

        async def mock_post(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            resp = _mock_response(500, {})
            resp.headers = {}
            return resp

        adapter._http = AsyncMock()
        adapter._http.post = mock_post

        with pytest.raises(httpx.HTTPStatusError):
            await adapter.chat(LLMRequest(
                messages=[Message(role="user", content="test")],
            ))

        assert call_count == 2  # 1 initial + 1 retry

    @pytest.mark.asyncio
    async def test_400_no_retry(self):
        """400 Bad Request should not retry."""
        adapter = LLMProxyAdapter(base_url="http://fake:8100", slot="test")
        call_count = 0

        async def mock_post(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            resp = _mock_response(400, {})
            resp.headers = {}
            return resp

        adapter._http = AsyncMock()
        adapter._http.post = mock_post

        with pytest.raises(httpx.HTTPStatusError):
            await adapter.chat(LLMRequest(
                messages=[Message(role="user", content="test")],
            ))

        assert call_count == 1  # No retry

    @pytest.mark.asyncio
    async def test_429_succeeds_on_second_attempt(self):
        """429 followed by success should return normal result."""
        adapter = LLMProxyAdapter(base_url="http://fake:8100", slot="test")
        call_count = 0

        async def mock_post(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                resp = _mock_response(429, {})
                resp.headers = {"Retry-After": "0"}
                return resp
            return _mock_response(200, {
                "choices": [{"message": {"content": "ok"}, "finish_reason": "stop"}],
                "usage": {"prompt_tokens": 10, "completion_tokens": 5},
            })

        adapter._http = AsyncMock()
        adapter._http.post = mock_post

        result = await adapter.chat(LLMRequest(
            messages=[Message(role="user", content="test")],
        ))
        assert result.content == "ok"
        assert call_count == 2


def test_proxy_adapter_capabilities_defaults():
    adapter = LLMProxyAdapter(base_url="http://localhost:8100", slot="primary")
    assert adapter.supports_tool_use() is True  # assume yes by default
    assert adapter.context_window_size() == 128_000  # default


def test_proxy_adapter_name():
    adapter = LLMProxyAdapter(base_url="http://localhost:8100", slot="primary")
    assert adapter.name() == "llm-proxy:primary"
