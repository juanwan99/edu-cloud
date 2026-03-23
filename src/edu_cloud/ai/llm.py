"""通用 LLM Chat 客户端 — 支持 OpenAI Chat 和 Anthropic Messages 两种 API 格式。

自动检测：URL 中含 "anthropic" → 走 Anthropic Messages API，否则走 OpenAI Chat。
"""
import json as _json
import logging
import httpx
from edu_cloud.ai.schemas import ChatMessage, ToolCall

logger = logging.getLogger(__name__)


class LLMChatClient:
    """非流式 chat completion 客户端，支持 tool_calls。自动适配 OpenAI/Anthropic。"""

    def __init__(
        self,
        api_url: str,
        api_key: str,
        model: str,
        timeout: int = 60,
        max_retries: int = 3,
        slot: str = "",
    ):
        self.api_url = api_url.rstrip("/")
        self.api_key = api_key
        self.model = model
        self.max_retries = max_retries
        self._slot = slot  # llm-proxy slot header
        self._http = httpx.AsyncClient(timeout=timeout)
        self._is_proxy = bool(slot)
        self._is_anthropic = not self._is_proxy and "anthropic" in self.api_url.lower()

    async def close(self):
        await self._http.aclose()

    async def chat(
        self,
        messages: list[ChatMessage],
        tools: list[dict] | None = None,
        temperature: float = 0.3,
    ) -> ChatMessage:
        """发送请求，自动选择 OpenAI 或 Anthropic 格式。proxy 模式统一走 OpenAI。"""
        if self._is_anthropic:
            return await self._chat_anthropic(messages, tools, temperature)
        return await self._chat_openai(messages, tools, temperature)

    # === OpenAI Chat Completions ===

    async def _chat_openai(self, messages, tools, temperature) -> ChatMessage:
        payload: dict = {
            "model": self.model,
            "messages": [m.to_dict() for m in messages],
            "temperature": temperature,
        }
        if tools:
            payload["tools"] = tools
            payload["tool_choice"] = "auto"

        headers = {"Content-Type": "application/json"}
        if self._is_proxy:
            headers["X-LLM-Slot"] = self._slot
        else:
            headers["Authorization"] = f"Bearer {self.api_key}"

        last_error = None
        for attempt in range(self.max_retries):
            try:
                resp = await self._http.post(
                    f"{self.api_url}/chat/completions",
                    json=payload,
                    headers=headers,
                )
                if resp.status_code != 200:
                    last_error = f"HTTP {resp.status_code}: {resp.text[:200]}"
                    logger.warning("LLM chat attempt %d/%d: %s", attempt + 1, self.max_retries, last_error)
                    continue

                data = resp.json()
                choices = data.get("choices") or []
                if not choices:
                    last_error = "Empty choices in LLM response"
                    logger.warning("LLM chat attempt %d/%d: %s", attempt + 1, self.max_retries, last_error)
                    continue

                msg = choices[0]["message"]
                tool_calls = None
                if msg.get("tool_calls"):
                    tool_calls = [ToolCall.from_openai(tc) for tc in msg["tool_calls"]]

                return ChatMessage(
                    role="assistant",
                    content=msg.get("content"),
                    tool_calls=tool_calls,
                )

            except (httpx.TimeoutException, httpx.ConnectError) as e:
                last_error = f"Network error: {e}"
                logger.warning("LLM chat attempt %d/%d: %s", attempt + 1, self.max_retries, last_error)

        raise RuntimeError(f"LLM chat failed after {self.max_retries} attempts: {last_error}")

    # === Anthropic Messages API ===

    async def _chat_anthropic(self, messages, tools, temperature) -> ChatMessage:
        # 分离 system prompt 和对话消息（Anthropic 的 system 是顶层字段）
        system_text = ""
        conv_messages = []
        for m in messages:
            if m.role == "system":
                system_text += (m.content or "") + "\n"
            elif m.role == "tool":
                # Anthropic 的 tool_result 格式
                conv_messages.append({
                    "role": "user",
                    "content": [{
                        "type": "tool_result",
                        "tool_use_id": m.tool_call_id,
                        "content": m.content or "",
                    }],
                })
            elif m.role == "assistant" and m.tool_calls:
                # assistant 的 tool_use
                content = []
                if m.content:
                    content.append({"type": "text", "text": m.content})
                for tc in m.tool_calls:
                    content.append({
                        "type": "tool_use",
                        "id": tc.id,
                        "name": tc.name,
                        "input": tc.arguments,
                    })
                conv_messages.append({"role": "assistant", "content": content})
            else:
                conv_messages.append({"role": m.role, "content": m.content or ""})

        payload: dict = {
            "model": self.model,
            "max_tokens": 4096,
            "messages": conv_messages,
            "temperature": temperature,
        }
        if system_text.strip():
            payload["system"] = system_text.strip()
        if tools:
            # 转换 OpenAI tool 格式 → Anthropic tool 格式
            payload["tools"] = [self._convert_tool_to_anthropic(t) for t in tools]

        headers = {
            "x-api-key": self.api_key,
            "anthropic-version": "2023-06-01",
            "Content-Type": "application/json",
        }

        last_error = None
        for attempt in range(self.max_retries):
            try:
                resp = await self._http.post(
                    self.api_url,  # Anthropic 端点不加路径后缀
                    json=payload,
                    headers=headers,
                )
                if resp.status_code != 200:
                    last_error = f"HTTP {resp.status_code}: {resp.text[:200]}"
                    logger.warning("LLM anthropic attempt %d/%d: %s", attempt + 1, self.max_retries, last_error)
                    continue

                data = resp.json()
                content_blocks = data.get("content") or []
                if not content_blocks:
                    last_error = "Empty content in Anthropic response"
                    continue

                # 解析 Anthropic 响应：可能有 text 和 tool_use 混合
                text_parts = []
                tool_calls = []
                for block in content_blocks:
                    if block["type"] == "text":
                        text_parts.append(block["text"])
                    elif block["type"] == "tool_use":
                        tool_calls.append(ToolCall(
                            id=block["id"],
                            name=block["name"],
                            arguments=block.get("input", {}),
                        ))

                return ChatMessage(
                    role="assistant",
                    content="\n".join(text_parts) if text_parts else None,
                    tool_calls=tool_calls if tool_calls else None,
                )

            except (httpx.TimeoutException, httpx.ConnectError) as e:
                last_error = f"Network error: {e}"
                logger.warning("LLM anthropic attempt %d/%d: %s", attempt + 1, self.max_retries, last_error)

        raise RuntimeError(f"LLM anthropic failed after {self.max_retries} attempts: {last_error}")

    @staticmethod
    def _convert_tool_to_anthropic(openai_tool: dict) -> dict:
        """OpenAI function tool → Anthropic tool 格式。"""
        func = openai_tool.get("function", openai_tool)
        return {
            "name": func["name"],
            "description": func.get("description", ""),
            "input_schema": func.get("parameters", {"type": "object", "properties": {}}),
        }
