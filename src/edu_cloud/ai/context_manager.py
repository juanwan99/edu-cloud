"""Context compression and token management (Design §6)."""
from __future__ import annotations

import logging
from edu_cloud.ai.llm_adapter import LLMProxyAdapter, LLMRequest
from edu_cloud.ai.schemas import Message

logger = logging.getLogger(__name__)

COMPACT_BUFFER = 13_000
SUMMARY_MAX_TOKENS = 20_000
KEEP_RECENT_TURNS = 4


class TokenCounter:
    @staticmethod
    def estimate(text: str) -> int:
        chinese_chars = sum(1 for c in text if '\u4e00' <= c <= '\u9fff')
        other_chars = len(text) - chinese_chars
        return int(chinese_chars * 1.5 + other_chars * 0.4)

    @staticmethod
    def estimate_messages(messages: list[Message]) -> int:
        total = 0
        for m in messages:
            if m.content:
                total += TokenCounter.estimate(m.content)
            if m.tool_calls:
                total += len(str(m.tool_calls)) // 3
        return total


class ContextManager:
    def should_compact(self, token_count: int, context_window: int) -> bool:
        threshold = context_window - COMPACT_BUFFER - SUMMARY_MAX_TOKENS
        return token_count > threshold

    async def compact(self, messages: list[Message], adapter: LLMProxyAdapter) -> list[Message]:
        if len(messages) < 3:
            return messages

        # F001: Count user turns backward to handle tool_calls/tool messages correctly.
        # A "turn" starts with a user message and includes all subsequent non-user messages.
        split_idx = self._find_turn_boundary(messages, KEEP_RECENT_TURNS)
        if split_idx <= 1:
            return messages

        system_msg = messages[0]
        early_messages = messages[1:split_idx]
        recent_messages = messages[split_idx:]

        summary = await self._summarize(early_messages, adapter)
        return [system_msg, Message(role="assistant", content=summary), *recent_messages]

    @staticmethod
    def _find_turn_boundary(messages: list[Message], keep_turns: int) -> int:
        """Find the index where recent turns start (counting user messages backward)."""
        user_count = 0
        for i in range(len(messages) - 1, 0, -1):
            if messages[i].role == "user":
                user_count += 1
                if user_count == keep_turns:
                    return i
        return 1  # keep everything except system

    async def _summarize(self, messages: list[Message], adapter: LLMProxyAdapter) -> str:
        prompt = (
            "请从以下对话中提取关键信息，按优先级保留：\n"
            "1. 已确认的数据发现（具体数字和结论）\n"
            "2. 用户的原始需求和约束\n"
            "3. 已完成的任务和未完成的任务\n"
            "4. 发现的异常和待验证的假设\n\n"
            "丢弃：工具调用的原始 JSON、重复的中间步骤、已被纠正的错误结论。\n"
            "用结构化列表输出，控制在 500 字以内。"
        )
        try:
            resp = await adapter.chat(LLMRequest(
                messages=[Message(role="system", content=prompt), *messages],
                max_tokens=2000,
                stream=False,
            ))
            return f"[对话摘要] {resp.content}"
        except Exception:
            logger.warning("Compact summarization failed, using fallback")
            contents = [m.content for m in messages if m.content]
            return f"[对话摘要 - 简略] 之前讨论了: {'; '.join(contents[:5])}"
