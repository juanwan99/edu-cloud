"""Analytics helper — effective score computation."""
import logging
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from edu_cloud.modules.grading.models import GradingResult
from edu_cloud.modules.scan.models import StudentAnswer
from edu_cloud.modules.exam.models import Question
from edu_cloud.modules.analytics.identity import resolve_student_identities

logger = logging.getLogger(__name__)


def _score_source(scan_score, final_score, ai_score, source) -> str:
    if final_score is not None:
        if source == "ai":
            return "ai_final"
        if source == "ai_override":
            return "ai_override"
        if source == "manual":
            return "manual"
        if ai_score is not None and float(final_score) == float(ai_score):
            return "ai_final"
        return "final"
    if scan_score is not None:
        return "objective_scan"
    return "missing"


async def get_effective_scores(
    db: AsyncSession, subject_id: str, school_id: str,
    visible_class_ids: list[str] | None = None,
    include_unmatched: bool | None = None,
) -> list[dict]:
    """Return effective scores for all answers in a subject.

    Effective score = COALESCE(GradingResult.final_score, StudentAnswer.score).
    max_score from Question table.
    """
    effective = func.coalesce(GradingResult.final_score, StudentAnswer.score)
    stmt = (
        select(
            StudentAnswer.id.label("answer_id"),
            StudentAnswer.student_id,
            StudentAnswer.question_id,
            StudentAnswer.score.label("scan_score"),
            StudentAnswer.detected_answer,
            StudentAnswer.is_anomaly,
            StudentAnswer.anomaly_type,
            StudentAnswer.question_type.label("answer_question_type"),
            effective.label("effective_score"),
            GradingResult.ai_score,
            GradingResult.ai_confidence,
            GradingResult.final_score,
            GradingResult.status.label("grading_status"),
            GradingResult.source.label("grading_source"),
            Question.max_score,
            Question.question_type,
        )
        .outerjoin(GradingResult, GradingResult.answer_id == StudentAnswer.id)
        .join(Question, Question.id == StudentAnswer.question_id)
        .where(
            StudentAnswer.subject_id == subject_id,
            StudentAnswer.school_id == school_id,
            StudentAnswer.is_absent.is_(False),
        )
    )

    result = await db.execute(stmt)
    rows = result.all()
    identities = await resolve_student_identities(
        db,
        school_id=school_id,
        raw_student_ids=[row.student_id for row in rows],
    )

    scores = []
    visible_set = set(visible_class_ids) if visible_class_ids is not None else None
    include_unmatched_rows = (
        include_unmatched
        if include_unmatched is not None
        else not any(identity.canonical_student_id for identity in identities.values())
    )
    for row in rows:
        if row.effective_score is None:
            continue
        identity = identities.get(row.student_id)
        if (not identity or identity.canonical_student_id is None) and not include_unmatched_rows:
            continue
        canonical_student_id = (
            identity.canonical_student_id if identity and identity.canonical_student_id else row.student_id
        )
        class_id = identity.class_id if identity else None
        if visible_set is not None and class_id not in visible_set:
            continue
        scores.append({
            "student_id": canonical_student_id,
            "raw_student_id": row.student_id,
            "canonical_student_id": canonical_student_id,
            "class_id": class_id,
            "student_number": identity.student_number if identity else None,
            "student_name": identity.name if identity else None,
            "match_method": identity.match_method if identity else None,
            "match_status": identity.match_status if identity else "unmatched",
            "answer_id": row.answer_id,
            "question_id": row.question_id,
            "effective_score": row.effective_score,
            "max_score": row.max_score,
            "question_type": row.question_type or row.answer_question_type,
            "detected_answer": row.detected_answer,
            "is_anomaly": row.is_anomaly,
            "anomaly_type": row.anomaly_type,
            "ai_score": row.ai_score,
            "ai_confidence": row.ai_confidence,
            "final_score": row.final_score,
            "grading_status": row.grading_status,
            "grading_source": row.grading_source,
            "score_source": _score_source(
                row.scan_score, row.final_score, row.ai_score, row.grading_source,
            ),
        })
    return scores


async def get_effective_scores_batch(
    db: AsyncSession, subject_ids: list[str], school_id: str,
    visible_class_ids: list[str] | None = None,
    include_unmatched: bool | None = None,
) -> dict[str, list[dict]]:
    """Batch version: one query for all subjects -> dict keyed by subject_id."""
    if not subject_ids:
        return {}
    effective = func.coalesce(GradingResult.final_score, StudentAnswer.score)
    stmt = (
        select(
            StudentAnswer.id.label("answer_id"),
            StudentAnswer.subject_id,
            StudentAnswer.student_id,
            StudentAnswer.question_id,
            StudentAnswer.score.label("scan_score"),
            StudentAnswer.detected_answer,
            StudentAnswer.is_anomaly,
            StudentAnswer.anomaly_type,
            StudentAnswer.question_type.label("answer_question_type"),
            effective.label("effective_score"),
            GradingResult.ai_score,
            GradingResult.ai_confidence,
            GradingResult.final_score,
            GradingResult.status.label("grading_status"),
            GradingResult.source.label("grading_source"),
            Question.max_score,
            Question.question_type,
        )
        .outerjoin(GradingResult, GradingResult.answer_id == StudentAnswer.id)
        .join(Question, Question.id == StudentAnswer.question_id)
        .where(
            StudentAnswer.subject_id.in_(subject_ids),
            StudentAnswer.school_id == school_id,
            StudentAnswer.is_absent.is_(False),
        )
    )

    result = await db.execute(stmt)
    rows = result.all()
    identities = await resolve_student_identities(
        db,
        school_id=school_id,
        raw_student_ids=[row.student_id for row in rows],
    )

    by_subject: dict[str, list[dict]] = {sid: [] for sid in subject_ids}
    visible_set = set(visible_class_ids) if visible_class_ids is not None else None
    include_unmatched_rows = (
        include_unmatched
        if include_unmatched is not None
        else not any(identity.canonical_student_id for identity in identities.values())
    )
    for row in rows:
        if row.effective_score is None:
            continue
        identity = identities.get(row.student_id)
        if (not identity or identity.canonical_student_id is None) and not include_unmatched_rows:
            continue
        canonical_student_id = (
            identity.canonical_student_id if identity and identity.canonical_student_id else row.student_id
        )
        class_id = identity.class_id if identity else None
        if visible_set is not None and class_id not in visible_set:
            continue
        by_subject.setdefault(row.subject_id, []).append({
            "student_id": canonical_student_id,
            "raw_student_id": row.student_id,
            "canonical_student_id": canonical_student_id,
            "class_id": class_id,
            "student_number": identity.student_number if identity else None,
            "student_name": identity.name if identity else None,
            "match_method": identity.match_method if identity else None,
            "match_status": identity.match_status if identity else "unmatched",
            "answer_id": row.answer_id,
            "question_id": row.question_id,
            "effective_score": row.effective_score,
            "max_score": row.max_score,
            "question_type": row.question_type or row.answer_question_type,
            "detected_answer": row.detected_answer,
            "is_anomaly": row.is_anomaly,
            "anomaly_type": row.anomaly_type,
            "ai_score": row.ai_score,
            "ai_confidence": row.ai_confidence,
            "final_score": row.final_score,
            "grading_status": row.grading_status,
            "grading_source": row.grading_source,
            "score_source": _score_source(
                row.scan_score, row.final_score, row.ai_score, row.grading_source,
            ),
        })
    return by_subject
