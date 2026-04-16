"""MemoryStore: CRUD + conflict merge for cross-session memory."""

from __future__ import annotations

import logging
from typing import Any

from sqlalchemy import delete, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from edu_cloud.models.memory import EntityMemory, ProjectState

logger = logging.getLogger(__name__)


def _deep_merge(base: dict, update: dict, *, _depth: int = 0) -> dict:
    """Recursively merge update into base. Returns new dict (no mutation).

    - dict + dict -> recursive merge (capped at depth 5 to prevent stack overflow)
    - anything else -> update wins
    """
    result = {**base}
    for k, v in update.items():
        if _depth < 5 and k in result and isinstance(result[k], dict) and isinstance(v, dict):
            result[k] = _deep_merge(result[k], v, _depth=_depth + 1)
        else:
            result[k] = v
    return result


class MemoryStore:
    """Persistent memory operations with school-level data isolation."""

    # ── EntityMemory ──

    async def upsert_entity(
        self,
        db: AsyncSession,
        school_id: str,
        entity_type: str,
        entity_id: str,
        facts: dict[str, Any],
    ) -> EntityMemory:
        """Create or update entity memory. New facts merge with existing (shallow)."""
        stmt = select(EntityMemory).where(
            EntityMemory.school_id == school_id,
            EntityMemory.entity_type == entity_type,
            EntityMemory.entity_id == entity_id,
        )
        result = await db.execute(stmt)
        existing = result.scalar_one_or_none()

        if existing is not None:
            merged = _deep_merge(existing.facts, facts)
            existing.facts = merged
            await db.flush()
            return existing

        mem = EntityMemory(
            entity_type=entity_type,
            entity_id=entity_id,
            school_id=school_id,
            facts=facts,
        )
        db.add(mem)
        await db.flush()
        return mem

    async def get_entities(
        self,
        db: AsyncSession,
        school_id: str,
        entity_type: str,
        entity_ids: list[str] | None = None,
        visible_student_ids: list[str] | None = None,
    ) -> list[EntityMemory]:
        """Get entity memories with school isolation + optional DataScope filtering.

        When entity_type="student" and visible_student_ids is provided,
        only entities whose entity_id is in visible_student_ids are returned
        (DataScope enforcement).
        """
        if entity_ids is not None and not entity_ids:
            return []

        # DataScope filtering for student entities
        if entity_type == "student" and visible_student_ids is not None:
            if not visible_student_ids:
                return []  # deny-all
            if entity_ids is not None:
                entity_ids = [eid for eid in entity_ids if eid in set(visible_student_ids)]
            else:
                entity_ids = visible_student_ids

        stmt = select(EntityMemory).where(
            EntityMemory.school_id == school_id,
            EntityMemory.entity_type == entity_type,
        )
        if entity_ids is not None:
            stmt = stmt.where(EntityMemory.entity_id.in_(entity_ids))

        result = await db.execute(stmt)
        return list(result.scalars().all())

    async def cleanup_episodes(
        self,
        db: AsyncSession,
        school_id: str,
        max_count: int = 50,
    ) -> int:
        """Remove oldest episodic memories exceeding max_count."""
        stmt = select(EntityMemory).where(
            EntityMemory.school_id == school_id,
            EntityMemory.entity_type == "session_episode",
        ).order_by(EntityMemory.updated_at.desc())

        result = await db.execute(stmt)
        all_episodes = list(result.scalars().all())

        if len(all_episodes) <= max_count:
            return 0

        to_delete = all_episodes[max_count:]
        ids_to_delete = [e.id for e in to_delete]
        await db.execute(
            delete(EntityMemory).where(EntityMemory.id.in_(ids_to_delete))
        )
        await db.flush()
        return len(ids_to_delete)

    # ── ProjectState ──

    async def save_project(
        self,
        db: AsyncSession,
        project_type: str,
        project_id: str,
        owner_id: str,
        school_id: str,
        state: dict[str, Any],
        status: str = "active",
    ) -> ProjectState:
        proj = ProjectState(
            project_type=project_type,
            project_id=project_id,
            owner_id=owner_id,
            school_id=school_id,
            state=state,
            status=status,
        )
        db.add(proj)
        await db.flush()
        return proj

    async def get_project(
        self,
        db: AsyncSession,
        project_id: str,
        owner_id: str,
        school_id: str,
    ) -> ProjectState | None:
        stmt = select(ProjectState).where(
            ProjectState.project_id == project_id,
            ProjectState.owner_id == owner_id,
            ProjectState.school_id == school_id,
        )
        result = await db.execute(stmt)
        return result.scalar_one_or_none()

    async def update_project_status(
        self,
        db: AsyncSession,
        project_id: str,
        owner_id: str,
        school_id: str,
        status: str,
    ) -> None:
        stmt = (
            update(ProjectState)
            .where(
                ProjectState.project_id == project_id,
                ProjectState.owner_id == owner_id,
                ProjectState.school_id == school_id,
            )
            .values(status=status)
        )
        await db.execute(stmt)
        await db.flush()

    async def update_project_state(
        self,
        db: AsyncSession,
        project_id: str,
        owner_id: str,
        school_id: str,
        state_updates: dict[str, Any],
    ) -> None:
        proj = await self.get_project(db, project_id, owner_id, school_id)
        if proj is not None:
            merged = _deep_merge(proj.state, state_updates)
            proj.state = merged
            await db.flush()

    async def get_active_projects(
        self,
        db: AsyncSession,
        owner_id: str,
        school_id: str,
    ) -> list[ProjectState]:
        stmt = select(ProjectState).where(
            ProjectState.owner_id == owner_id,
            ProjectState.school_id == school_id,
            ProjectState.status == "active",
        )
        result = await db.execute(stmt)
        return list(result.scalars().all())
