"""年级聚合分析服务 — WP-D: 年级维度统计 + 考情趋势。

按 Grade → Class → Student → ExamResult 链路聚合，
填补好分数 D 轴最后一个缺口。
"""
import logging
import statistics as _statistics

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from edu_cloud.models.grade import Grade
from edu_cloud.modules.exam.models import Exam, Subject, Question
from edu_cloud.modules.student.models import Class, Student
from edu_cloud.modules.analytics import get_effective_scores_batch
from edu_cloud.modules.analytics.service import _verify_exam, _get_subjects, _get_max_by_subject
from edu_cloud.modules.analytics.segment_service import get_segment_config, compute_segments
from edu_cloud.services.exceptions import NotFoundError

logger = logging.getLogger(__name__)


async def _verify_grade(db: AsyncSession, grade_id: str, school_id: str) -> Grade:
    """Load and verify grade belongs to school."""
    result = await db.execute(
        select(Grade).where(Grade.id == grade_id, Grade.school_id == school_id)
    )
    grade = result.scalar_one_or_none()
    if not grade:
        raise NotFoundError("Grade not found")
    return grade


async def _get_grade_class_ids(db: AsyncSession, grade_id: str, school_id: str) -> list[str]:
    """Get all class IDs belonging to a grade."""
    result = await db.execute(
        select(Class.id).where(
            Class.grade_id == grade_id,
            Class.school_id == school_id,
        )
    )
    return [row[0] for row in result.all()]


async def _get_grade_exams(
    db: AsyncSession, grade_id: str, school_id: str, limit: int = 10,
) -> list[Exam]:
    """Get recent exams for a grade, sorted by exam_date asc.

    An exam belongs to a grade if any student in that grade's classes has answers for it.
    """
    class_ids = await _get_grade_class_ids(db, grade_id, school_id)
    if not class_ids:
        return []

    # Find exams where students from these classes have data
    from edu_cloud.modules.scan.models import StudentAnswer
    subq = (
        select(StudentAnswer.exam_id)
        .join(Student, Student.id == StudentAnswer.student_id)
        .where(
            Student.class_id.in_(class_ids),
            StudentAnswer.school_id == school_id,
        )
        .distinct()
        .subquery()
    )

    result = await db.execute(
        select(Exam)
        .where(
            Exam.id.in_(select(subq.c.exam_id)),
            Exam.school_id == school_id,
        )
        .order_by(Exam.exam_date.asc())
        .limit(limit)
    )
    return list(result.scalars().all())


async def get_grade_overview(
    db: AsyncSession, school_id: str, grade_id: str, exam_id: str,
) -> dict:
    """年级概览：某次考试中该年级各班级的聚合数据。

    Returns:
        {
            grade_name, exam_name,
            classes: [{class_name, avg_score, pass_rate, excellent_rate,
                       max_score, min_score, median}]
        }
    """
    grade = await _verify_grade(db, grade_id, school_id)
    exam = await _verify_exam(db, exam_id, school_id)

    class_ids = await _get_grade_class_ids(db, grade_id, school_id)
    if not class_ids:
        return {
            "grade_name": grade.name, "exam_name": exam.name, "classes": [],
        }

    # Load subjects for this exam
    subjects = await _get_subjects(db, exam_id, school_id)
    subj_ids = [s.id for s in subjects]
    if not subj_ids:
        return {
            "grade_name": grade.name, "exam_name": exam.name, "classes": [],
        }

    max_by_subject = await _get_max_by_subject(db, subj_ids, school_id)
    total_max = sum(max_by_subject.get(s.id, 0.0) for s in subjects)

    # Get scores for all subjects (no class filter -- we filter ourselves)
    scores_by_subject = await get_effective_scores_batch(db, subj_ids, school_id)

    # Aggregate per student
    student_totals: dict[str, float] = {}
    for subj in subjects:
        for s in scores_by_subject.get(subj.id, []):
            student_totals[s["student_id"]] = (
                student_totals.get(s["student_id"], 0.0) + s["effective_score"]
            )

    # Map students to classes
    student_ids = list(student_totals.keys())
    student_class_map: dict[str, str] = {}
    if student_ids:
        result = await db.execute(
            select(Student.id, Student.class_id).where(Student.id.in_(student_ids))
        )
        student_class_map = {row.id: row.class_id for row in result.all()}

    # Group by class (only grade's classes)
    class_ids_set = set(class_ids)
    class_scores: dict[str, list[float]] = {}
    for sid, score in student_totals.items():
        cid = student_class_map.get(sid)
        if cid and cid in class_ids_set:
            class_scores.setdefault(cid, []).append(score)

    # Load class names
    class_names: dict[str, str] = {}
    if class_ids:
        result = await db.execute(
            select(Class.id, Class.name).where(Class.id.in_(class_ids))
        )
        class_names = {row.id: row.name for row in result.all()}

    # Segment config for pass/excellent rates
    boundaries, labels = await get_segment_config(db, school_id)

    classes = []
    for cid, scores_list in class_scores.items():
        n = len(scores_list)
        if n == 0:
            continue
        avg = round(sum(scores_list) / n, 2)
        max_s = max(scores_list)
        min_s = min(scores_list)
        median = round(_statistics.median(scores_list), 2)

        # Pass/excellent rates using segment boundaries
        segs = compute_segments(scores_list, total_max, boundaries, labels)
        # "优秀" is first segment (>= 85%), "及格" means not in last segment
        excellent_count = segs[0]["count"] if segs else 0
        fail_count = segs[-1]["count"] if segs else 0
        pass_count = n - fail_count

        classes.append({
            "class_id": cid,
            "class_name": class_names.get(cid, ""),
            "avg_score": avg,
            "pass_rate": round(pass_count / n, 4) if n > 0 else 0,
            "excellent_rate": round(excellent_count / n, 4) if n > 0 else 0,
            "max_score": max_s,
            "min_score": min_s,
            "median": median,
            "student_count": n,
        })

    classes.sort(key=lambda x: -x["avg_score"])

    return {
        "grade_name": grade.name,
        "exam_name": exam.name,
        "exam_id": exam_id,
        "classes": classes,
    }


async def get_grade_exam_trend(
    db: AsyncSession, school_id: str, grade_id: str, limit: int = 10,
) -> dict:
    """年级考情趋势：该年级最近 N 次考试的年级级别聚合。

    Returns:
        {
            points: [{exam_id, exam_name, exam_date, avg_score,
                      pass_rate, excellent_rate, student_count}]
        }
    """
    grade = await _verify_grade(db, grade_id, school_id)
    class_ids = await _get_grade_class_ids(db, grade_id, school_id)
    if not class_ids:
        return {"grade_name": grade.name, "points": []}

    exams = await _get_grade_exams(db, grade_id, school_id, limit)
    if not exams:
        return {"grade_name": grade.name, "points": []}

    boundaries, labels = await get_segment_config(db, school_id)
    class_ids_set = set(class_ids)
    points = []

    for exam in exams:
        subjects = await _get_subjects(db, exam.id, school_id)
        subj_ids = [s.id for s in subjects]
        if not subj_ids:
            continue

        max_by_subject = await _get_max_by_subject(db, subj_ids, school_id)
        total_max = sum(max_by_subject.get(s.id, 0.0) for s in subjects)

        scores_by_subject = await get_effective_scores_batch(db, subj_ids, school_id)

        # Aggregate per student
        student_totals: dict[str, float] = {}
        for subj in subjects:
            for s in scores_by_subject.get(subj.id, []):
                student_totals[s["student_id"]] = (
                    student_totals.get(s["student_id"], 0.0) + s["effective_score"]
                )

        # Filter to grade's students
        student_ids = list(student_totals.keys())
        if not student_ids:
            continue
        result = await db.execute(
            select(Student.id, Student.class_id).where(Student.id.in_(student_ids))
        )
        student_class_map = {row.id: row.class_id for row in result.all()}

        grade_values = [
            score for sid, score in student_totals.items()
            if student_class_map.get(sid) in class_ids_set
        ]

        n = len(grade_values)
        if n == 0:
            continue

        avg = round(sum(grade_values) / n, 2)
        segs = compute_segments(grade_values, total_max, boundaries, labels)
        excellent_count = segs[0]["count"] if segs else 0
        fail_count = segs[-1]["count"] if segs else 0
        pass_count = n - fail_count

        points.append({
            "exam_id": exam.id,
            "exam_name": exam.name,
            "exam_date": exam.exam_date.isoformat() if exam.exam_date else None,
            "avg_score": avg,
            "pass_rate": round(pass_count / n, 4) if n > 0 else 0,
            "excellent_rate": round(excellent_count / n, 4) if n > 0 else 0,
            "student_count": n,
        })

    return {"grade_name": grade.name, "points": points}


async def get_grade_subject_comparison(
    db: AsyncSession, school_id: str, grade_id: str, exam_id: str,
) -> dict:
    """年级科目对比：某次考试中该年级各科目的聚合数据。

    Returns:
        {
            subjects: [{subject_code, subject_name, avg_score,
                        max_possible, score_rate, difficulty}]
        }
    """
    grade = await _verify_grade(db, grade_id, school_id)
    exam = await _verify_exam(db, exam_id, school_id)

    class_ids = await _get_grade_class_ids(db, grade_id, school_id)
    if not class_ids:
        return {
            "grade_name": grade.name, "exam_name": exam.name, "subjects": [],
        }

    subjects = await _get_subjects(db, exam_id, school_id)
    subj_ids = [s.id for s in subjects]
    if not subj_ids:
        return {
            "grade_name": grade.name, "exam_name": exam.name, "subjects": [],
        }

    max_by_subject = await _get_max_by_subject(db, subj_ids, school_id)
    class_ids_set = set(class_ids)

    # Get all student→class mapping in one batch
    scores_by_subject = await get_effective_scores_batch(db, subj_ids, school_id)

    # Collect all student IDs across all subjects
    all_student_ids: set[str] = set()
    for subj in subjects:
        for s in scores_by_subject.get(subj.id, []):
            all_student_ids.add(s["student_id"])

    student_class_map: dict[str, str] = {}
    if all_student_ids:
        result = await db.execute(
            select(Student.id, Student.class_id).where(
                Student.id.in_(list(all_student_ids))
            )
        )
        student_class_map = {row.id: row.class_id for row in result.all()}

    subject_stats = []
    for subj in subjects:
        max_possible = max_by_subject.get(subj.id, 0.0)
        scores = scores_by_subject.get(subj.id, [])

        # Filter to grade's students: per-student total within this subject
        student_subject_totals: dict[str, float] = {}
        for s in scores:
            sid = s["student_id"]
            if student_class_map.get(sid) in class_ids_set:
                student_subject_totals[sid] = (
                    student_subject_totals.get(sid, 0.0) + s["effective_score"]
                )

        values = list(student_subject_totals.values())
        n = len(values)
        if n == 0:
            avg = 0.0
            score_rate = 0.0
        else:
            avg = round(sum(values) / n, 2)
            score_rate = round(avg / max_possible, 4) if max_possible > 0 else 0.0

        # Difficulty: 1 - score_rate (higher difficulty = lower score_rate)
        difficulty = round(1 - score_rate, 4) if max_possible > 0 else 0.0

        subject_stats.append({
            "subject_code": subj.code,
            "subject_name": subj.name,
            "avg_score": avg,
            "max_possible": max_possible,
            "score_rate": score_rate,
            "difficulty": difficulty,
            "student_count": n,
        })

    return {
        "grade_name": grade.name,
        "exam_name": exam.name,
        "exam_id": exam_id,
        "subjects": subject_stats,
    }
