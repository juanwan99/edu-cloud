"""Analytics helper — effective score computation."""
import logging
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from edu_cloud.modules.grading.models import AIGradingResult, TeacherReview
from edu_cloud.modules.scan.models import StudentAnswer
from edu_cloud.modules.student.models import Student

logger = logging.getLogger(__name__)


async def get_effective_scores(
    db: AsyncSession, subject_id: str, school_id: str,
    visible_class_ids: list[str] | None = None,
) -> list[dict]:
    """Return effective scores for all graded answers in a subject."""
    stmt = (
        select(
            StudentAnswer.student_id,
            AIGradingResult.question_id,
            AIGradingResult.score,
            AIGradingResult.max_score,
            AIGradingResult.review_status,
            TeacherReview.adjusted_score,
        )
        .join(AIGradingResult, AIGradingResult.answer_id == StudentAnswer.id)
        .outerjoin(TeacherReview, TeacherReview.result_id == AIGradingResult.id)
        .where(
            StudentAnswer.subject_id == subject_id,
            StudentAnswer.school_id == school_id,
            AIGradingResult.school_id == school_id,
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
        if row.review_status == "overridden" and row.adjusted_score is None:
            logger.warning(
                "overridden result has adjusted_score=None, "
                "falling back to AI score for student_id=%s question_id=%s",
                row.student_id, row.question_id,
            )
        effective = (
            row.adjusted_score
            if row.review_status == "overridden" and row.adjusted_score is not None
            else row.score
        )
        scores.append({
            "student_id": row.student_id,
            "question_id": row.question_id,
            "effective_score": effective,
            "max_score": row.max_score,
        })
    return scores
