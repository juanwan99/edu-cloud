"""Extract and persist key findings from agent sessions (Design §6)."""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass

from edu_cloud.ai.llm_adapter import LLMProxyAdapter, LLMRequest
from edu_cloud.ai.schemas import Message

logger = logging.getLogger(__name__)


@dataclass
class MemoryEntry:
    memory_type: str  # finding | preference | follow_up
    content: str
    entity_type: str | None = None
    entity_id: str | None = None


class SessionMemoryExtractor:
    async def extract(self, messages: list[Message], adapter: LLMProxyAdapter) -> list[MemoryEntry]:
        prompt = (
            "从这段对话中提取值得跨会话记住的信息。返回 JSON 数组，每项包含：\n"
            '- type: "finding" | "preference" | "follow_up"\n'
            '- content: 一句话描述\n'
            '- entity_type: "student" | "class" | "school" | null\n'
            '- entity_id: 关联 ID 或 null\n\n'
            "只提取重要发现、用户偏好、待跟进事项。不要提取临时数据。\n"
            "如果没有值得记住的，返回空数组 []。"
        )
        try:
            resp = await adapter.chat(LLMRequest(
                messages=[Message(role="system", content=prompt), *messages],
                max_tokens=1000,
                stream=False,
            ))
            return self._parse(resp.content)
        except Exception:
            logger.warning("Memory extraction failed")
            return []

    @staticmethod
    def _parse(raw: str) -> list[MemoryEntry]:
        try:
            text = raw.strip()
            if text.startswith("```"):
                text = text.split("\n", 1)[-1].rsplit("```", 1)[0]
            items = json.loads(text)
            if not isinstance(items, list):
                return []
            return [
                MemoryEntry(
                    memory_type=item.get("type", "finding"),
                    content=item.get("content", ""),
                    entity_type=item.get("entity_type"),
                    entity_id=item.get("entity_id"),
                )
                for item in items
                if item.get("content")
            ]
        except (json.JSONDecodeError, KeyError, TypeError):
            return []
