"""Analytics helper — effective score computation."""
import logging
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from edu_cloud.modules.grading.models import GradingResult
from edu_cloud.modules.scan.models import StudentAnswer
from edu_cloud.modules.student.models import Student

logger = logging.getLogger(__name__)


async def get_effective_scores(
    db: AsyncSession, subject_id: str, school_id: str,
    visible_class_ids: list[str] | None = None,
) -> list[dict]:
    """Return effective scores for all graded answers in a subject.

    Effective score = GradingResult.final_score（单一权威源）。
    """
    stmt = (
        select(
            StudentAnswer.student_id,
            GradingResult.question_id,
            GradingResult.final_score,
            GradingResult.max_score,
            GradingResult.status,
        )
        .join(GradingResult, GradingResult.answer_id == StudentAnswer.id)
        .where(
            StudentAnswer.subject_id == subject_id,
            StudentAnswer.school_id == school_id,
            GradingResult.school_id == school_id,
        )
    )
    if visible_class_ids is not None:
        stmt = stmt.join(Student, Student.id == StudentAnswer.student_id).where(
            Student.class_id.in_(visible_class_ids)
        )

    result = await db.execute(stmt)
    rows = result.all()

    scores = []
    for row in rows:
        if row.final_score is None:
            logger.warning(
                "grading_result missing final_score: student=%s question=%s status=%s",
                row.student_id, row.question_id, row.status,
            )
            continue
        scores.append({
            "student_id": row.student_id,
            "question_id": row.question_id,
            "effective_score": row.final_score,
            "max_score": row.max_score,
        })
    return scores


async def get_effective_scores_batch(
    db: AsyncSession, subject_ids: list[str], school_id: str,
    visible_class_ids: list[str] | None = None,
) -> dict[str, list[dict]]:
    """Batch version: one query for all subjects → dict keyed by subject_id."""
    if not subject_ids:
        return {}
    stmt = (
        select(
            StudentAnswer.subject_id,
            StudentAnswer.student_id,
            GradingResult.question_id,
            GradingResult.final_score,
            GradingResult.max_score,
            GradingResult.status,
        )
        .join(GradingResult, GradingResult.answer_id == StudentAnswer.id)
        .where(
            StudentAnswer.subject_id.in_(subject_ids),
            StudentAnswer.school_id == school_id,
            GradingResult.school_id == school_id,
        )
    )
    if visible_class_ids is not None:
        stmt = stmt.join(Student, Student.id == StudentAnswer.student_id).where(
            Student.class_id.in_(visible_class_ids)
        )

    result = await db.execute(stmt)

    by_subject: dict[str, list[dict]] = {sid: [] for sid in subject_ids}
    for row in result.all():
        if row.final_score is None:
            continue
        by_subject.setdefault(row.subject_id, []).append({
            "student_id": row.student_id,
            "question_id": row.question_id,
            "effective_score": row.final_score,
            "max_score": row.max_score,
        })
    return by_subject
