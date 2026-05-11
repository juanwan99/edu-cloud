"""Scope-filtered entity resolvers for AI ref picker."""
from __future__ import annotations

import logging
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from edu_cloud.ai.ref_types import RefItem

logger = logging.getLogger(__name__)


async def resolve_exam(db: AsyncSession, school_id: str, search: str | None,
                       parent_id: str | None, limit: int) -> list[RefItem]:
    from edu_cloud.modules.exam.models import Exam
    q = select(Exam).where(Exam.school_id == school_id)
    if search:
        q = q.where(Exam.name.ilike(f"%{search}%"))
    q = q.order_by(Exam.created_at.desc()).limit(limit)
    rows = (await db.execute(q)).scalars().all()
    return [RefItem(id=str(e.id), label=e.name,
                    subtitle=e.status, children_type="subject") for e in rows]


async def resolve_subject(db: AsyncSession, school_id: str, search: str | None,
                          parent_id: str | None, limit: int) -> list[RefItem]:
    if not parent_id:
        return []
    from edu_cloud.modules.exam.models import Subject
    q = select(Subject).where(Subject.exam_id == parent_id)
    if search:
        q = q.where(Subject.name.ilike(f"%{search}%"))
    q = q.limit(limit)
    rows = (await db.execute(q)).scalars().all()
    return [RefItem(id=str(s.id), label=s.name,
                    subtitle=s.code, children_type="question") for s in rows]


async def resolve_class(db: AsyncSession, school_id: str, search: str | None,
                        parent_id: str | None, limit: int) -> list[RefItem]:
    from edu_cloud.models.class_group import ClassGroup
    q = select(ClassGroup).where(ClassGroup.school_id == school_id)
    if search:
        q = q.where(ClassGroup.name.ilike(f"%{search}%"))
    q = q.order_by(ClassGroup.name).limit(limit)
    rows = (await db.execute(q)).scalars().all()
    return [RefItem(id=str(c.id), label=c.name,
                    subtitle=c.grade, children_type="student") for c in rows]


async def resolve_student(db: AsyncSession, school_id: str, search: str | None,
                          parent_id: str | None, limit: int) -> list[RefItem]:
    from edu_cloud.models.student import Student
    q = select(Student).where(Student.school_id == school_id)
    if parent_id:
        q = q.where(Student.class_id == parent_id)
    if search:
        q = q.where(Student.name.ilike(f"%{search}%"))
    q = q.order_by(Student.name).limit(limit)
    rows = (await db.execute(q)).scalars().all()
    return [RefItem(id=str(s.id), label=s.name,
                    subtitle=s.student_number) for s in rows]


async def resolve_question(db: AsyncSession, school_id: str, search: str | None,
                           parent_id: str | None, limit: int) -> list[RefItem]:
    if not parent_id:
        return []
    from edu_cloud.modules.exam.models import Question
    q = select(Question).where(Question.subject_id == parent_id)
    if search:
        q = q.where(Question.name.ilike(f"%{search}%"))
    q = q.limit(limit)
    rows = (await db.execute(q)).scalars().all()
    return [RefItem(id=str(qn.id), label=qn.name or "题目",
                    subtitle=f"{qn.max_score}分") for qn in rows]


RESOLVERS: dict[str, Any] = {
    "exam": resolve_exam,
    "subject": resolve_subject,
    "class": resolve_class,
    "student": resolve_student,
    "question": resolve_question,
}
