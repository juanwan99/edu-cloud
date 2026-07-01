"""Service facade for AI reference resolver data access."""
from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from edu_cloud.models.class_group import ClassGroup
from edu_cloud.models.student import Student
from edu_cloud.modules.exam.models import Exam, Question, Subject


@dataclass(frozen=True)
class RefRecord:
    id: str
    label: str
    subtitle: str | None = None
    children_type: str | None = None


async def resolve_exam(
    db: AsyncSession,
    school_id: str,
    search: str | None,
    parent_id: str | None,
    limit: int,
) -> list[RefRecord]:
    q = select(Exam).where(Exam.school_id == school_id)
    if search:
        q = q.where(Exam.name.ilike(f"%{search}%"))
    q = q.order_by(Exam.created_at.desc()).limit(limit)
    rows = (await db.execute(q)).scalars().all()
    return [
        RefRecord(id=str(exam.id), label=exam.name, subtitle=exam.status, children_type="subject")
        for exam in rows
    ]


async def resolve_subject(
    db: AsyncSession,
    school_id: str,
    search: str | None,
    parent_id: str | None,
    limit: int,
) -> list[RefRecord]:
    if not parent_id:
        return []
    q = select(Subject).where(Subject.exam_id == parent_id)
    if search:
        q = q.where(Subject.name.ilike(f"%{search}%"))
    q = q.limit(limit)
    rows = (await db.execute(q)).scalars().all()
    return [
        RefRecord(
            id=str(subject.id),
            label=subject.name,
            subtitle=subject.code,
            children_type="question",
        )
        for subject in rows
    ]


async def resolve_class(
    db: AsyncSession,
    school_id: str,
    search: str | None,
    parent_id: str | None,
    limit: int,
) -> list[RefRecord]:
    q = select(ClassGroup).where(ClassGroup.school_id == school_id)
    if search:
        q = q.where(ClassGroup.name.ilike(f"%{search}%"))
    q = q.order_by(ClassGroup.name).limit(limit)
    rows = (await db.execute(q)).scalars().all()
    return [
        RefRecord(
            id=str(class_group.id),
            label=class_group.name,
            subtitle=class_group.grade,
            children_type="student",
        )
        for class_group in rows
    ]


async def resolve_student(
    db: AsyncSession,
    school_id: str,
    search: str | None,
    parent_id: str | None,
    limit: int,
) -> list[RefRecord]:
    q = select(Student).where(Student.school_id == school_id)
    if parent_id:
        q = q.where(Student.class_id == parent_id)
    if search:
        q = q.where(Student.name.ilike(f"%{search}%"))
    q = q.order_by(Student.name).limit(limit)
    rows = (await db.execute(q)).scalars().all()
    return [
        RefRecord(id=str(student.id), label=student.name, subtitle=student.student_number)
        for student in rows
    ]


async def resolve_question(
    db: AsyncSession,
    school_id: str,
    search: str | None,
    parent_id: str | None,
    limit: int,
) -> list[RefRecord]:
    if not parent_id:
        return []
    q = select(Question).where(Question.subject_id == parent_id)
    if search:
        q = q.where(Question.name.ilike(f"%{search}%"))
    q = q.limit(limit)
    rows = (await db.execute(q)).scalars().all()
    return [
        RefRecord(
            id=str(question.id),
            label=question.name or "题目",
            subtitle=f"{question.max_score}分",
        )
        for question in rows
    ]
