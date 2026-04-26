"""Analytics helper — effective score computation."""
import logging
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from edu_cloud.modules.grading.models import GradingResult
from edu_cloud.modules.scan.models import StudentAnswer
from edu_cloud.modules.student.models import Student
from edu_cloud.modules.exam.models import Question

logger = logging.getLogger(__name__)


async def get_effective_scores(
    db: AsyncSession, subject_id: str, school_id: str,
    visible_class_ids: list[str] | None = None,
) -> list[dict]:
    """Return effective scores for all answers in a subject.

    Effective score = COALESCE(GradingResult.final_score, StudentAnswer.score).
    max_score from Question table.
    """
    effective = func.coalesce(GradingResult.final_score, StudentAnswer.score)
    stmt = (
        select(
            StudentAnswer.student_id,
            StudentAnswer.question_id,
            effective.label("effective_score"),
            Question.max_score,
        )
        .outerjoin(GradingResult, GradingResult.answer_id == StudentAnswer.id)
        .join(Question, Question.id == StudentAnswer.question_id)
        .where(
            StudentAnswer.subject_id == subject_id,
            StudentAnswer.school_id == school_id,
        )
    )
    if visible_class_ids is not None:
        stmt = stmt.join(Student, Student.id == StudentAnswer.student_id).where(
            Student.class_id.in_(visible_class_ids)
        )

    result = await db.execute(stmt)

    scores = []
    for row in result.all():
        if row.effective_score is None:
            continue
        scores.append({
            "student_id": row.student_id,
            "question_id": row.question_id,
            "effective_score": row.effective_score,
            "max_score": row.max_score,
        })
    return scores


async def get_effective_scores_batch(
    db: AsyncSession, subject_ids: list[str], school_id: str,
    visible_class_ids: list[str] | None = None,
) -> dict[str, list[dict]]:
    """Batch version: one query for all subjects -> dict keyed by subject_id."""
    if not subject_ids:
        return {}
    effective = func.coalesce(GradingResult.final_score, StudentAnswer.score)
    stmt = (
        select(
            StudentAnswer.subject_id,
            StudentAnswer.student_id,
            StudentAnswer.question_id,
            effective.label("effective_score"),
            Question.max_score,
        )
        .outerjoin(GradingResult, GradingResult.answer_id == StudentAnswer.id)
        .join(Question, Question.id == StudentAnswer.question_id)
        .where(
            StudentAnswer.subject_id.in_(subject_ids),
            StudentAnswer.school_id == school_id,
        )
    )
    if visible_class_ids is not None:
        stmt = stmt.join(Student, Student.id == StudentAnswer.student_id).where(
            Student.class_id.in_(visible_class_ids)
        )

    result = await db.execute(stmt)

    by_subject: dict[str, list[dict]] = {sid: [] for sid in subject_ids}
    for row in result.all():
        if row.effective_score is None:
            continue
        by_subject.setdefault(row.subject_id, []).append({
            "student_id": row.student_id,
            "question_id": row.question_id,
            "effective_score": row.effective_score,
            "max_score": row.max_score,
        })
    return by_subject
