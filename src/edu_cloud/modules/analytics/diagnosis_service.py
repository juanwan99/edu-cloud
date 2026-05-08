"""三维班级知识点诊断。"""
import math
from collections import defaultdict

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from edu_cloud.modules.analytics.models import StudentKnpMastery
from edu_cloud.modules.student.models import Student

UNMASTER_THRESHOLD = 0.6


async def _get_concept_ids_for_subject(
    db: AsyncSession, exam_id: str, school_id: str, subject_id: str,
) -> set[str]:
    """Return concept_ids linked to questions of the given subject via QKP."""
    from edu_cloud.modules.exam.models import Subject, Question
    from edu_cloud.modules.knowledge.models import QuestionKnowledgePoint

    subj = (await db.execute(
        select(Subject.id).where(
            Subject.id == subject_id,
            Subject.exam_id == exam_id,
            Subject.school_id == school_id,
        )
    )).scalar_one_or_none()
    if not subj:
        return set()

    rows = (await db.execute(
        select(QuestionKnowledgePoint.concept_id).distinct()
        .join(Question, Question.id == QuestionKnowledgePoint.question_id)
        .where(
            Question.subject_id == subject_id,
            Question.school_id == school_id,
        )
    )).scalars().all()
    return set(rows)


async def class_diagnosis(
    db: AsyncSession, *, exam_id: str, school_id: str,
    subject_id: str | None = None,
    class_id: str | None = None,
    visible_class_ids: list[str] | None = None,
) -> dict:
    effective_class_ids = [class_id] if class_id else visible_class_ids

    # Resolve concept_ids when subject_id is specified
    subject_concept_ids: set[str] | None = None
    if subject_id:
        subject_concept_ids = await _get_concept_ids_for_subject(
            db, exam_id, school_id, subject_id,
        )
        if not subject_concept_ids:
            return {
                "worstKnowledges": [],
                "unmasterMaxCntKnowledges": [],
                "maxScoreDiffKnowledges": [],
                "weakKnpCount": 0,
                "filtered_by_subject": True,
            }

    stmt = (
        select(StudentKnpMastery)
        .join(Student, Student.id == StudentKnpMastery.student_id)
        .where(
            StudentKnpMastery.exam_id == exam_id,
            StudentKnpMastery.school_id == school_id,
        )
    )
    if effective_class_ids is not None:
        stmt = stmt.where(Student.class_id.in_(effective_class_ids))
    if subject_concept_ids is not None:
        stmt = stmt.where(StudentKnpMastery.concept_id.in_(subject_concept_ids))

    rows = list((await db.execute(stmt)).scalars().all())
    if not rows:
        return {
            "worstKnowledges": [],
            "unmasterMaxCntKnowledges": [],
            "maxScoreDiffKnowledges": [],
            "weakKnpCount": 0,
        }

    kp_rates: dict[str, list[float]] = defaultdict(list)
    for r in rows:
        kp_rates[r.concept_id].append(float(r.stu_rate))

    total_kps = len(kp_rates)

    # worstKnowledges: 按班级平均掌握率升序 Top5
    kp_avg = [
        {"concept_id": kp, "rate": round(sum(rates) / len(rates), 4)}
        for kp, rates in kp_rates.items()
    ]
    kp_avg.sort(key=lambda x: x["rate"])
    worst = kp_avg[:5]

    # unmasterMaxCntKnowledges: stu_rate < 0.6 的学生数降序 Top5
    kp_unmaster = [
        {"concept_id": kp, "count": sum(1 for r in rates if r < UNMASTER_THRESHOLD)}
        for kp, rates in kp_rates.items()
    ]
    kp_unmaster.sort(key=lambda x: (-x["count"], x["concept_id"]))
    unmaster = kp_unmaster[:5]

    # maxScoreDiffKnowledges: (max - min) 降序 Top5
    kp_diff = [
        {"concept_id": kp, "diff": round(max(rates) - min(rates), 4)}
        for kp, rates in kp_rates.items()
    ]
    kp_diff.sort(key=lambda x: (-x["diff"], x["concept_id"]))
    max_diff = kp_diff[:5]

    weak_count = math.floor(total_kps * 0.3)

    result = {
        "worstKnowledges": worst,
        "unmasterMaxCntKnowledges": unmaster,
        "maxScoreDiffKnowledges": max_diff,
        "weakKnpCount": weak_count,
    }
    if subject_id:
        result["filtered_by_subject"] = True
    return result
