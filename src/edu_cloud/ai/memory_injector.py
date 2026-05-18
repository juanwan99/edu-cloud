"""MemoryInjector: load relevant memories at session start for system prompt."""

from __future__ import annotations

import json
import logging

from sqlalchemy.ext.asyncio import AsyncSession

from edu_cloud.ai.memory_store import MemoryStore

logger = logging.getLogger(__name__)

_MAX_EPISODES = 5

# Roles with school-wide memory access (can see all student memories passively)
_FULL_SCOPE_ROLES = frozenset({
    "platform_admin",
    "district_admin",
    "school_admin",
    "principal",
    "academic_director",
    "admin",  # compat alias
})


class MemoryInjector:
    """Loads cross-session memories and formats for system prompt injection."""

    def __init__(
        self,
        store: MemoryStore | None = None,
        max_tokens: int = 2000,
    ):
        self._store = store or MemoryStore()
        self._max_tokens = max_tokens

    async def build_context(
        self,
        db: AsyncSession,
        school_id: str,
        user_id: str,
        role: str | None = None,
        class_ids: list[str] | None = None,
        student_ids: list[str] | None = None,
    ) -> str:
        """Build memory context for system prompt. Returns empty string if none found.

        Scope safety:
        - student_ids provided (parent): filter by student_ids
        - class_ids provided but no student_ids (teacher): skip student memories (safe default)
        - neither (principal/admin): load all student memories
        """
        sections: list[str] = []
        char_budget = self._max_tokens * 2

        try:
            is_full_scope = role in _FULL_SCOPE_ROLES

            for etype in ("student", "teacher", "class"):
                eids = None
                if etype == "student":
                    if student_ids is not None:
                        eids = student_ids
                    elif not is_full_scope:
                        # Non-admin roles (teachers, grade leaders, homeroom, parents):
                        # Skip student memories in passive injection (safe default).
                        # Teachers can use memory_read tool for active queries instead.
                        continue
                    # else: full school access (principal/admin), load all
                else:
                    # teacher/class entity types: only load when scope is established
                    if not is_full_scope and class_ids is None:
                        # No scope context — skip to avoid injecting irrelevant/noisy data
                        continue

                entities = await self._store.get_entities(
                    db, school_id, etype, entity_ids=eids,
                    visible_student_ids=student_ids,
                )
                if entities:
                    lines = [
                        f"[{etype}] {e.entity_id}: {json.dumps(e.facts, ensure_ascii=False)}"
                        for e in entities
                    ]
                    sections.append("\n".join(lines))

            # Episodic memories (last N)
            episodes = await self._store.get_entities(db, school_id, "session_episode")
            if episodes:
                recent = episodes[-_MAX_EPISODES:]
                lines = [f"[历史] {e.facts.get('summary', '')}" for e in recent]
                sections.append("\n".join(lines))

            # Active projects
            projects = await self._store.get_active_projects(db, user_id, school_id)
            if projects:
                lines = []
                for p in projects:
                    checkpoint = p.state.get("checkpoint", "unknown")
                    topic = p.state.get("topic", p.project_id)
                    lines.append(
                        f"[进行中/{p.project_type}] {topic} — 当前阶段: {checkpoint}"
                    )
                sections.append("\n".join(lines))

        except Exception:
            logger.exception("Memory injection failed (non-blocking)")
            return ""

        if not sections:
            return ""

        full_text = "\n\n".join(sections)

        if len(full_text) > char_budget:
            full_text = full_text[:char_budget] + "\n... (记忆已截断)"

        return f"\n\n【已知上下文（跨会话记忆）】\n{full_text}"
