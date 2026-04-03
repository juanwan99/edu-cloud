"""Unified LLM adapter — routes all calls through llm-proxy (Design §5)."""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from typing import Any, AsyncGenerator, Protocol

import httpx

from edu_cloud.ai.schemas import Message, ToolCall

logger = logging.getLogger(__name__)


@dataclass
class TokenUsage:
    input_tokens: int = 0
    output_tokens: int = 0

    @property
    def total(self) -> int:
        return self.input_tokens + self.output_tokens


@dataclass
class LLMRequest:
    messages: list[Message]
    tools: list[dict] | None = None
    model: str | None = None
    temperature: float = 0.7
    max_tokens: int = 4096
    stream: bool = True


@dataclass
class LLMResponse:
    content: str | None = None
    tool_calls: list[ToolCall] | None = None
    usage: TokenUsage = field(default_factory=TokenUsage)
    stop_reason: str = "end_turn"
    raw: dict | None = None


@dataclass
class LLMChunk:
    """One chunk in a streaming response."""
    delta_content: str | None = None
    delta_tool_call: dict | None = None
    finish_reason: str | None = None


class LLMAdapter(Protocol):
    """Protocol that all LLM adapters implement."""

    async def chat(self, request: LLMRequest) -> LLMResponse: ...
    async def chat_stream(self, request: LLMRequest) -> AsyncGenerator[LLMChunk, None]: ...
    def supports_tool_use(self) -> bool: ...
    def supports_parallel_tool_calls(self) -> bool: ...
    def context_window_size(self) -> int: ...
    def name(self) -> str: ...


class LLMProxyAdapter:
    """Calls llm-proxy via OpenAI-compatible API. Slot header selects the provider."""

    def __init__(
        self,
        base_url: str = "http://localhost:8100",
        slot: str = "primary",
        timeout: int = 120,
        context_window: int = 128_000,
    ):
        self._base_url = base_url.rstrip("/")
        self._slot = slot
        self._context_window = context_window
        self._http = httpx.AsyncClient(timeout=timeout)
        self._cached_capabilities: dict | None = None

    async def close(self):
        await self._http.aclose()

    def name(self) -> str:
        return f"llm-proxy:{self._slot}"

    def supports_tool_use(self) -> bool:
        if self._cached_capabilities:
            return self._cached_capabilities.get("tool_use", True)
        return True

    def supports_parallel_tool_calls(self) -> bool:
        if self._cached_capabilities:
            return self._cached_capabilities.get("parallel_tools", False)
        return False

    def context_window_size(self) -> int:
        return self._context_window

    def set_capabilities(self, caps: dict) -> None:
        self._cached_capabilities = caps
        if "context_window" in caps:
            self._context_window = caps["context_window"]

    async def chat(self, request: LLMRequest) -> LLMResponse:
        payload = self._build_payload(request)
        resp = await self._http.post(
            f"{self._base_url}/v1/chat/completions",
            headers={"X-Slot": self._slot},
            json=payload,
        )
        resp.raise_for_status()
        return self._parse_response(resp.json())

    async def chat_stream(self, request: LLMRequest) -> AsyncGenerator[LLMChunk, None]:
        payload = self._build_payload(request)
        payload["stream"] = True
        async with self._http.stream(
            "POST",
            f"{self._base_url}/v1/chat/completions",
            headers={"X-Slot": self._slot},
            json=payload,
        ) as resp:
            resp.raise_for_status()
            async for line in resp.aiter_lines():
                if not line.startswith("data: "):
                    continue
                data_str = line[6:]
                if data_str == "[DONE]":
                    break
                chunk_data = json.loads(data_str)
                delta = chunk_data.get("choices", [{}])[0].get("delta", {})
                yield LLMChunk(
                    delta_content=delta.get("content"),
                    delta_tool_call=delta.get("tool_calls", [None])[0] if delta.get("tool_calls") else None,
                    finish_reason=chunk_data.get("choices", [{}])[0].get("finish_reason"),
                )

    def _build_payload(self, request: LLMRequest) -> dict:
        payload: dict[str, Any] = {
            "messages": [m.to_dict() for m in request.messages],
            "temperature": request.temperature,
            "max_tokens": request.max_tokens,
            "stream": False,
        }
        if request.model:
            payload["model"] = request.model
        if request.tools:
            payload["tools"] = request.tools
        return payload

    @staticmethod
    def _parse_response(data: dict) -> LLMResponse:
        choice = data.get("choices", [{}])[0]
        message = choice.get("message", {})
        usage_raw = data.get("usage", {})

        # Parse tool calls
        tool_calls = None
        raw_tcs = message.get("tool_calls")
        if raw_tcs:
            tool_calls = [ToolCall.from_openai(tc) for tc in raw_tcs]

        # Map finish_reason
        finish = choice.get("finish_reason", "stop")
        stop_reason = "tool_use" if finish in ("tool_calls", "function_call") else "end_turn"

        return LLMResponse(
            content=message.get("content"),
            tool_calls=tool_calls,
            usage=TokenUsage(
                input_tokens=usage_raw.get("prompt_tokens", 0),
                output_tokens=usage_raw.get("completion_tokens", 0),
            ),
            stop_reason=stop_reason,
            raw=data,
        )
