"""Shared student identity resolution (module-external).

Scan data can store either the canonical ``students.id`` or an external
barcode/student key in ``student_answers.student_id``. Any consumer that
aggregates by student must group by the canonical student whenever it can be
resolved, while still preserving the raw key for audit and unmatched-row
warnings.

This lives in the module-external services layer so that both ``analytics`` and
``pipeline`` can share one canonical resolver without a cross-module dependency
(D-03B): ``pipeline`` must not import ``edu_cloud.modules.analytics``.
``edu_cloud.modules.analytics.identity`` re-exports these symbols for backward
compatibility.
"""
from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from edu_cloud.modules.student.models import Student


@dataclass(frozen=True)
class StudentIdentity:
    raw_student_id: str
    canonical_student_id: str | None
    class_id: str | None
    student_number: str | None
    name: str | None
    match_method: str | None
    match_status: str


def _unique_map(pairs: list[tuple[str | None, Student]]) -> dict[str, Student]:
    seen: dict[str, Student | None] = {}
    for key, student in pairs:
        if not key:
            continue
        if key in seen and seen[key] is not None and seen[key].id != student.id:
            seen[key] = None
        else:
            seen[key] = student
    return {k: v for k, v in seen.items() if v is not None}


def _jingyan_barcode_key(student_number: str | None) -> str | None:
    if not student_number or len(student_number) < 4:
        return None
    return "25" + student_number[-4:]


def _identity(raw_student_id: str, student: Student, method: str) -> StudentIdentity:
    return StudentIdentity(
        raw_student_id=raw_student_id,
        canonical_student_id=student.id,
        class_id=student.class_id,
        student_number=student.student_number,
        name=student.name,
        match_method=method,
        match_status="matched",
    )


async def resolve_student_identities(
    db: AsyncSession,
    *,
    school_id: str,
    raw_student_ids: list[str] | set[str] | tuple[str, ...],
) -> dict[str, StudentIdentity]:
    """Resolve raw answer keys to canonical student identities.

    Match order:
    1. raw key equals ``students.id``.
    2. raw key equals ``students.student_number``.
    3. Jingyan barcode convention: ``25`` + last four digits of student_number.
    """
    raw_ids = [str(sid) for sid in dict.fromkeys(raw_student_ids) if sid is not None]
    if not raw_ids:
        return {}

    result = await db.execute(select(Student).where(Student.school_id == school_id))
    students = list(result.scalars().all())

    by_id = _unique_map([(s.id, s) for s in students])
    by_number = _unique_map([(s.student_number, s) for s in students])
    by_jingyan = _unique_map([(_jingyan_barcode_key(s.student_number), s) for s in students])

    resolved: dict[str, StudentIdentity] = {}
    for raw in raw_ids:
        if raw in by_id:
            resolved[raw] = _identity(raw, by_id[raw], "student_id")
        elif raw in by_number:
            resolved[raw] = _identity(raw, by_number[raw], "student_number")
        elif raw in by_jingyan:
            resolved[raw] = _identity(raw, by_jingyan[raw], "jingyan_25_last4")
        else:
            resolved[raw] = StudentIdentity(
                raw_student_id=raw,
                canonical_student_id=None,
                class_id=None,
                student_number=None,
                name=None,
                match_method=None,
                match_status="unmatched",
            )
    return resolved
