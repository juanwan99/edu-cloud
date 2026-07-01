"""Scope-filtered entity resolvers for AI ref picker."""
from __future__ import annotations

from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from edu_cloud.ai.ref_types import RefItem
from edu_cloud.services import ai_ref_resolvers as ref_resolver_service


def _to_ref_items(records: list[ref_resolver_service.RefRecord]) -> list[RefItem]:
    return [
        RefItem(
            id=record.id,
            label=record.label,
            subtitle=record.subtitle,
            children_type=record.children_type,
        )
        for record in records
    ]


async def resolve_exam(db: AsyncSession, school_id: str, search: str | None,
                       parent_id: str | None, limit: int) -> list[RefItem]:
    records = await ref_resolver_service.resolve_exam(db, school_id, search, parent_id, limit)
    return _to_ref_items(records)


async def resolve_subject(db: AsyncSession, school_id: str, search: str | None,
                          parent_id: str | None, limit: int) -> list[RefItem]:
    records = await ref_resolver_service.resolve_subject(db, school_id, search, parent_id, limit)
    return _to_ref_items(records)


async def resolve_class(db: AsyncSession, school_id: str, search: str | None,
                        parent_id: str | None, limit: int) -> list[RefItem]:
    records = await ref_resolver_service.resolve_class(db, school_id, search, parent_id, limit)
    return _to_ref_items(records)


async def resolve_student(db: AsyncSession, school_id: str, search: str | None,
                          parent_id: str | None, limit: int) -> list[RefItem]:
    records = await ref_resolver_service.resolve_student(db, school_id, search, parent_id, limit)
    return _to_ref_items(records)


async def resolve_question(db: AsyncSession, school_id: str, search: str | None,
                           parent_id: str | None, limit: int) -> list[RefItem]:
    records = await ref_resolver_service.resolve_question(db, school_id, search, parent_id, limit)
    return _to_ref_items(records)


RESOLVERS: dict[str, Any] = {
    "exam": resolve_exam,
    "subject": resolve_subject,
    "class": resolve_class,
    "student": resolve_student,
    "question": resolve_question,
}
