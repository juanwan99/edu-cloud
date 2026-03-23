"""统计分析业务逻辑（从 exam-ai 迁入）。"""
import logging
import statistics

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from edu_cloud.modules.exam.models import Exam, Subject, Question
from edu_cloud.modules.student.models import Class, Student
from edu_cloud.modules.analytics import get_effective_scores
from edu_cloud.services.exceptions import NotFoundError, PermissionDeniedError

logger = logging.getLogger(__name__)

K_ANONYMITY_THRESHOLD = 5


async def _verify_exam(db: AsyncSession, exam_id: str, school_id: str) -> Exam:
    result = await db.execute(
        select(Exam).where(Exam.id == exam_id, Exam.school_id == school_id)
    )
    exam = result.scalar_one_or_none()
    if not exam:
        raise NotFoundError("Exam not found")
    return exam


async def _get_subjects(
    db: AsyncSession, exam_id: str, school_id: str,
    visible_subject_codes: list[str] | None = None,
    subject_id: str | None = None,
) -> list[Subject]:
    if subject_id:
        query = select(Subject).where(
            Subject.id == subject_id, Subject.exam_id == exam_id,
            Subject.school_id == school_id,
        )
        if visible_subject_codes is not None:
            query = query.where(Subject.code.in_(visible_subject_codes))
        result = await db.execute(query)
        subjects = list(result.scalars().all())
        if not subjects:
            raise NotFoundError("Subject not found")
        return subjects
    else:
        query = select(Subject).where(Subject.exam_id == exam_id, Subject.school_id == school_id)
        if visible_subject_codes is not None:
            query = query.where(Subject.code.in_(visible_subject_codes))
        result = await db.execute(query)
        return list(result.scalars().all())


async def _get_max_by_subject(
    db: AsyncSession, subject_ids: list[str], school_id: str
) -> dict[str, float]:
    q_result = await db.execute(
        select(
            Question.subject_id,
            func.sum(Question.max_score).label("max_possible"),
        )
        .where(Question.subject_id.in_(subject_ids), Question.school_id == school_id)
        .group_by(Question.subject_id)
    )
    return {row.subject_id: row.max_possible for row in q_result.all()}


async def exam_summary(
    db: AsyncSession, *, exam_id: str, school_id: str,
    visible_subject_codes: list[str] | None = None,
    visible_class_ids: list[str] | None = None,
) -> dict:
    await _verify_exam(db, exam_id, school_id)
    subjects = await _get_subjects(db, exam_id, school_id, visible_subject_codes)
    subject_ids = [s.id for s in subjects]
    if not subject_ids:
        return {"exam_id": exam_id, "total_students": 0, "subjects": []}

    max_by_subject = await _get_max_by_subject(db, subject_ids, school_id)
    all_students: set[str] = set()
    subject_stats = []

    for subj in subjects:
        max_possible = max_by_subject.get(subj.id, 0.0)
        scores = await get_effective_scores(db, subj.id, school_id, visible_class_ids)
        student_totals: dict[str, float] = {}
        for s in scores:
            all_students.add(s["student_id"])
            student_totals[s["student_id"]] = student_totals.get(s["student_id"], 0.0) + s["effective_score"]

        graded_count = len(student_totals)
        if student_totals:
            values = list(student_totals.values())
            avg = sum(values) / len(values)
            highest = max(values)
            lowest = min(values)
            score_rate = round(avg / max_possible, 4) if max_possible > 0 else 0.0
        else:
            avg = highest = lowest = score_rate = None

        subject_stats.append({
            "subject_id": subj.id, "subject_name": subj.name,
            "avg_score": round(avg, 2) if avg is not None else None,
            "max_score_possible": max_possible, "score_rate": score_rate,
            "highest": highest, "lowest": lowest, "graded_count": graded_count,
        })

    return {"exam_id": exam_id, "total_students": len(all_students), "subjects": subject_stats}


async def exam_distribution(
    db: AsyncSession, *, exam_id: str, school_id: str,
    subject_id: str | None = None,
    visible_subject_codes: list[str] | None = None,
    visible_class_ids: list[str] | None = None,
) -> dict:
    await _verify_exam(db, exam_id, school_id)
    subjects = await _get_subjects(db, exam_id, school_id, visible_subject_codes, subject_id)
    subj_ids = [s.id for s in subjects]
    max_by_subject = await _get_max_by_subject(db, subj_ids, school_id)

    student_totals: dict[str, float] = {}
    total_max = sum(max_by_subject.get(s.id, 0.0) for s in subjects)
    for subj in subjects:
        scores = await get_effective_scores(db, subj.id, school_id, visible_class_ids)
        for s in scores:
            student_totals[s["student_id"]] = student_totals.get(s["student_id"], 0.0) + s["effective_score"]

    intervals = [
        {"range": "0-59", "min_pct": 0, "max_pct": 60},
        {"range": "60-69", "min_pct": 60, "max_pct": 70},
        {"range": "70-79", "min_pct": 70, "max_pct": 80},
        {"range": "80-89", "min_pct": 80, "max_pct": 90},
        {"range": "90-100", "min_pct": 90, "max_pct": 101},
    ]
    total = len(student_totals)
    result_intervals = []
    for iv in intervals:
        count = sum(1 for score in student_totals.values()
                    if iv["min_pct"] <= ((score / total_max * 100) if total_max > 0 else 0) < iv["max_pct"])
        result_intervals.append({
            "range": iv["range"], "count": count,
            "percentage": round(count / total, 4) if total > 0 else 0,
        })

    return {"exam_id": exam_id, "subject_id": subject_id, "intervals": result_intervals, "total_students": total}


async def subject_question_analysis(
    db: AsyncSession, *, subject_id: str, school_id: str,
    visible_subject_codes: list[str] | None = None,
    visible_class_ids: list[str] | None = None,
) -> dict:
    result = await db.execute(
        select(Subject).where(Subject.id == subject_id, Subject.school_id == school_id)
    )
    subject = result.scalar_one_or_none()
    if not subject:
        raise NotFoundError("Subject not found")
    if visible_subject_codes is not None and subject.code not in visible_subject_codes:
        raise PermissionDeniedError("无权访问该科目")

    q_result = await db.execute(
        select(Question).where(Question.subject_id == subject_id, Question.school_id == school_id)
    )
    questions = {q.id: q for q in q_result.scalars().all()}
    scores = await get_effective_scores(db, subject_id, school_id, visible_class_ids)

    by_question: dict[str, list[float]] = {}
    for s in scores:
        by_question.setdefault(s["question_id"], []).append(s["effective_score"])

    question_stats = []
    for qid, q in questions.items():
        q_scores = by_question.get(qid, [])
        count = len(q_scores)
        avg = sum(q_scores) / count if count > 0 else 0.0
        score_rate = round(avg / q.max_score, 4) if q.max_score > 0 else 0.0
        question_stats.append({
            "question_id": qid, "question_name": q.name, "question_type": q.question_type,
            "max_score": q.max_score, "avg_score": round(avg, 2),
            "score_rate": score_rate, "graded_count": count,
        })

    return {"subject_id": subject_id, "subject_name": subject.name, "questions": question_stats}


async def grade_aggregates(
    db: AsyncSession, *, exam_id: str, school_id: str,
    subject_id: str | None = None,
    visible_subject_codes: list[str] | None = None,
    visible_class_ids: list[str] | None = None,
) -> dict:
    await _verify_exam(db, exam_id, school_id)
    subjects = await _get_subjects(db, exam_id, school_id, visible_subject_codes, subject_id)

    student_scores: dict[str, float] = {}
    for subj in subjects:
        scores = await get_effective_scores(db, subj.id, school_id)
        for s in scores:
            student_scores[s["student_id"]] = student_scores.get(s["student_id"], 0.0) + s["effective_score"]

    student_ids = list(student_scores.keys())
    student_class_map: dict[str, str] = {}
    if student_ids:
        result = await db.execute(
            select(Student.id, Student.class_id).where(Student.id.in_(student_ids))
        )
        student_class_map = {row.id: row.class_id for row in result.all()}

    all_values = list(student_scores.values())
    total_count = len(all_values)
    k_note = None

    if total_count >= K_ANONYMITY_THRESHOLD:
        q1, q2, q3 = statistics.quantiles(all_values, n=4)
        grade_stats = {
            "avg_score": round(statistics.mean(all_values), 2),
            "median_score": round(q2, 2), "p25": round(q1, 2), "p75": round(q3, 2),
            "student_count": total_count,
        }
    elif total_count > 0:
        grade_stats = {"avg_score": None, "median_score": None, "p25": None, "p75": None, "student_count": total_count}
        k_note = f"年级总人数 {total_count} 低于 k-匿名阈值 {K_ANONYMITY_THRESHOLD}"
    else:
        grade_stats = {"avg_score": None, "median_score": None, "p25": None, "p75": None, "student_count": 0}

    class_scores: dict[str, list[float]] = {}
    for sid, score in student_scores.items():
        cid = student_class_map.get(sid)
        if cid:
            class_scores.setdefault(cid, []).append(score)

    class_ids_list = list(class_scores.keys())
    class_names: dict[str, str] = {}
    if class_ids_list:
        result = await db.execute(select(Class.id, Class.name).where(Class.id.in_(class_ids_list)))
        class_names = {row.id: row.name for row in result.all()}

    class_entries = []
    for cid, scores_list in class_scores.items():
        count = len(scores_list)
        avg = round(statistics.mean(scores_list), 2) if count >= K_ANONYMITY_THRESHOLD else None
        is_my_class = visible_class_ids is not None and cid in visible_class_ids
        class_entries.append({
            "class_id": cid, "class_name": class_names.get(cid, ""),
            "avg_score": avg, "student_count": count, "my_class": is_my_class,
        })

    class_entries.sort(key=lambda x: (x["avg_score"] is None, -(x["avg_score"] or 0)))
    for i, entry in enumerate(class_entries):
        entry["rank"] = i + 1

    return {
        "exam_id": exam_id, "subject_id": subject_id,
        "grade_stats": grade_stats, "class_rankings": class_entries, "k_anonymity_note": k_note,
    }


async def get_student_exam_scores(
    db: AsyncSession, *, exam_id: str, student_id: str, school_id: str,
) -> list[dict]:
    subjects = await _get_subjects(db, exam_id, school_id)
    all_scores = []
    for subj in subjects:
        scores = await get_effective_scores(db, subj.id, school_id)
        for s in scores:
            if s["student_id"] == student_id:
                all_scores.append({
                    "subject_name": subj.name, "question_id": s["question_id"],
                    "score": s["effective_score"], "max_score": s["max_score"],
                })
    return all_scores
