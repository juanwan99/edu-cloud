"""Shared ownership chain verification for StudentAnswer write paths.

All endpoints writing StudentAnswer must verify the full chain:
  school → exam → subject → question

This module centralizes the invariant that was previously scattered
across individual routes with inconsistent coverage.
"""

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from edu_cloud.modules.exam.models import Exam, Question, Subject


async def verify_exam_subject_chain(
    db: AsyncSession,
    *,
    school_id: str,
    exam_id: str,
    subject_id: str,
) -> tuple[Exam, Subject]:
    """Verify exam belongs to school AND subject belongs to exam+school."""
    exam = (await db.execute(
        select(Exam).where(
            Exam.id == exam_id,
            Exam.school_id == school_id,
        )
    )).scalar_one_or_none()
    if not exam:
        raise HTTPException(404, "Exam not found")

    subject = (await db.execute(
        select(Subject).where(
            Subject.id == subject_id,
            Subject.exam_id == exam_id,
            Subject.school_id == school_id,
        )
    )).scalar_one_or_none()
    if not subject:
        raise HTTPException(404, "Subject not found in this exam")

    return exam, subject


async def verify_exam_subject_question_chain(
    db: AsyncSession,
    *,
    school_id: str,
    exam_id: str,
    subject_id: str,
    question_id: str,
) -> tuple[Exam, Subject, Question]:
    """Verify full chain: exam→subject→question all belong together."""
    exam, subject = await verify_exam_subject_chain(
        db, school_id=school_id, exam_id=exam_id, subject_id=subject_id,
    )

    question = (await db.execute(
        select(Question).where(
            Question.id == question_id,
            Question.subject_id == subject_id,
            Question.school_id == school_id,
        )
    )).scalar_one_or_none()
    if not question:
        raise HTTPException(404, "Question not found in this subject")

    return exam, subject, question


async def verify_questions_belong_to_subject(
    db: AsyncSession,
    *,
    school_id: str,
    subject_id: str,
    question_ids: list[str],
) -> dict[str, Question]:
    """Batch verify all question_ids belong to subject+school. Returns {id: Question}."""
    unique_ids = list(dict.fromkeys(question_ids))
    if not unique_ids:
        return {}

    questions = (await db.execute(
        select(Question).where(
            Question.id.in_(unique_ids),
            Question.subject_id == subject_id,
            Question.school_id == school_id,
        )
    )).scalars().all()

    by_id = {q.id: q for q in questions}
    missing = [qid for qid in unique_ids if qid not in by_id]
    if missing:
        raise HTTPException(
            404, f"Question {missing[0]} not found in subject {subject_id}"
        )
    return by_id
