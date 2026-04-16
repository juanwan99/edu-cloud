"""MemoryExtractor: extract + persist cross-session memories from conversation."""

from __future__ import annotations

import json
import logging
import re
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from edu_cloud.ai.llm_adapter import LLMProxyAdapter, LLMRequest
from edu_cloud.ai.memory_store import MemoryStore
from edu_cloud.ai.schemas import Message

logger = logging.getLogger(__name__)

_EXTRACT_PROMPT = """\
你是记忆提取器。从以下对话中提取值得跨会话保存的信息。

提取两类：
1. entity — 关于特定实体（学生/教师/班级）的事实
2. episode — 本次会话的关键决策或发现摘要

回复 JSON 数组，每项格式：
- entity: {"type": "entity", "entity_type": "student|teacher|class", "entity_id": "ID", "facts": {"key": "value"}}
- episode: {"type": "episode", "summary": "一句话摘要"}

如果没有值得保存的信息，回复 []。只回复 JSON，不要其他内容。
"""

_MAX_EPISODES = 50


class MemoryExtractor:
    """Extract memories from conversation and persist via MemoryStore."""

    def __init__(self, store: MemoryStore | None = None):
        self._store = store or MemoryStore()

    async def extract_and_persist(
        self,
        db: AsyncSession,
        messages: list[Message],
        adapter: LLMProxyAdapter,
        school_id: str,
        user_id: str,
        session_id: str,
    ) -> None:
        """Extract memories from messages and persist. Never raises."""
        if not messages:
            return

        try:
            entries = await self._extract(messages, adapter)
            if not entries:
                return
            await self._persist(db, entries, school_id, user_id, session_id)
            await self._store.cleanup_episodes(db, school_id, max_count=_MAX_EPISODES)
        except Exception:
            logger.exception("Memory extraction failed (non-blocking)")

    async def _extract(self, messages: list[Message], adapter: LLMProxyAdapter) -> list[dict[str, Any]]:
        conversation = "\n".join(
            f"{m.role}: {m.content}" for m in messages
            if m.role in ("user", "assistant") and m.content
        )
        if not conversation.strip():
            return []

        resp = await adapter.chat(LLMRequest(
            messages=[
                Message(role="system", content=_EXTRACT_PROMPT),
                Message(role="user", content=conversation[-6000:]),
            ],
            max_tokens=1000,
            stream=False,
        ))
        return self._parse(resp.content or "")

    @staticmethod
    def _parse(text: str) -> list[dict[str, Any]]:
        text = text.strip()
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
        try:
            data = json.loads(text)
            if not isinstance(data, list):
                return []
            return [e for e in data if isinstance(e, dict) and "type" in e]
        except (json.JSONDecodeError, ValueError):
            return []

    async def _persist(self, db: AsyncSession, entries: list[dict[str, Any]], school_id: str, user_id: str, session_id: str) -> None:
        for entry in entries:
            entry_type = entry.get("type")
            if entry_type == "entity":
                entity_type = entry.get("entity_type", "")
                entity_id = entry.get("entity_id", "")
                facts = entry.get("facts", {})
                if entity_type and entity_id and facts:
                    await self._store.upsert_entity(
                        db, school_id=school_id,
                        entity_type=entity_type,
                        entity_id=entity_id,
                        facts=facts,
                    )
            elif entry_type == "episode":
                summary = entry.get("summary", "")
                if summary:
                    await self._store.upsert_entity(
                        db, school_id=school_id,
                        entity_type="session_episode",
                        entity_id=session_id,
                        facts={"summary": summary, "user_id": user_id},
                    )
