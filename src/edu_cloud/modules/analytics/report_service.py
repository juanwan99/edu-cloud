"""自定义分析构建器 + 跨考试对比 + PDF 导出。"""
import logging
import statistics as _statistics

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from edu_cloud.modules.exam.models import Exam
from edu_cloud.modules.analytics.service import (
    exam_summary, exam_distribution, grade_aggregates,
    subject_question_analysis, _get_subjects, _get_max_by_subject,
)
from edu_cloud.modules.analytics import get_effective_scores
from edu_cloud.modules.analytics.segment_service import get_segment_config, compute_segments
from edu_cloud.modules.student.models import Class, Student
from edu_cloud.models.agent_snapshot import ExamAnalysisSnapshot, ClassExamReport
from edu_cloud.modules.profile.models import StudentExamSnapshot
from edu_cloud.services.exceptions import NotFoundError

logger = logging.getLogger(__name__)


async def build_report(
    db: AsyncSession,
    school_id: str,
    exam_ids: list[str],
    metrics: list[str] | None = None,
    subject_codes: list[str] | None = None,
    class_ids: list[str] | None = None,
    visible_subject_codes: list[str] | None = None,
    visible_class_ids: list[str] | None = None,
) -> dict:
    """自定义分析构建器：按指定维度聚合分析结果。"""
    all_metrics = metrics or ["summary", "segments", "ranking", "questions", "top_bottom"]
    result_metrics: dict = {}

    for exam_id in exam_ids:
        exam_result = await db.execute(
            select(Exam).where(Exam.id == exam_id, Exam.school_id == school_id)
        )
        exam = exam_result.scalar_one_or_none()
        if not exam:
            raise NotFoundError(f"Exam {exam_id} not found")

    primary_exam_id = exam_ids[0]

    effective_subject_codes = visible_subject_codes
    if subject_codes:
        if visible_subject_codes:
            effective_subject_codes = [c for c in subject_codes if c in visible_subject_codes]
        else:
            effective_subject_codes = subject_codes

    effective_class_ids = visible_class_ids
    if class_ids:
        if visible_class_ids:
            effective_class_ids = [c for c in class_ids if c in visible_class_ids]
        else:
            effective_class_ids = class_ids

    if "summary" in all_metrics:
        result_metrics["summary"] = await exam_summary(
            db, exam_id=primary_exam_id, school_id=school_id,
            visible_subject_codes=effective_subject_codes,
            visible_class_ids=effective_class_ids,
        )

    if "segments" in all_metrics:
        result_metrics["segments"] = await exam_distribution(
            db, exam_id=primary_exam_id, school_id=school_id,
            visible_subject_codes=effective_subject_codes,
            visible_class_ids=effective_class_ids,
        )

    if "ranking" in all_metrics:
        result_metrics["ranking"] = await grade_aggregates(
            db, exam_id=primary_exam_id, school_id=school_id,
            visible_subject_codes=effective_subject_codes,
            visible_class_ids=effective_class_ids,
        )

    if "questions" in all_metrics:
        subjects = await _get_subjects(db, primary_exam_id, school_id, effective_subject_codes)
        questions_data = []
        for subj in subjects:
            qa = await subject_question_analysis(
                db, subject_id=subj.id, school_id=school_id,
                visible_subject_codes=effective_subject_codes,
                visible_class_ids=effective_class_ids,
            )
            questions_data.append(qa)
        result_metrics["questions"] = questions_data

    if "top_bottom" in all_metrics:
        subjects = await _get_subjects(db, primary_exam_id, school_id, effective_subject_codes)
        student_totals: dict[str, float] = {}
        for subj in subjects:
            scores = await get_effective_scores(db, subj.id, school_id, effective_class_ids)
            for s in scores:
                student_totals[s["student_id"]] = student_totals.get(s["student_id"], 0) + s["effective_score"]

        ranked = sorted(student_totals.items(), key=lambda x: x[1], reverse=True)
        n = len(ranked)
        top_n = max(1, n // 10)
        student_rows = (await db.execute(
            select(Student.id, Student.name, Student.class_id, Class.name.label("class_name"))
            .outerjoin(Class, Class.id == Student.class_id)
            .where(Student.school_id == school_id, Student.id.in_(list(student_totals.keys())))
        )).all() if student_totals else []
        student_meta = {
            row.id: {
                "name": row.name,
                "class_id": row.class_id,
                "class_name": row.class_name,
            }
            for row in student_rows
        }

        def _ranked_row(student_id: str, score: float) -> dict:
            meta = student_meta.get(student_id, {})
            return {
                "student_id": student_id,
                "name": meta.get("name") or student_id,
                "class_id": meta.get("class_id"),
                "class_name": meta.get("class_name"),
                "score": round(score, 2),
            }

        result_metrics["top_bottom"] = {
            "top_10pct": [_ranked_row(sid, sc) for sid, sc in ranked[:top_n]],
            "bottom_10pct": [_ranked_row(sid, sc) for sid, sc in ranked[-top_n:]],
            "total_students": n,
        }

    return {
        "exam_ids": exam_ids,
        "metrics": result_metrics,
    }


async def get_grade_trend(
    db: AsyncSession,
    school_id: str,
    exam_ids: list[str],
    subject_code: str | None = None,
    visible_subject_codes: list[str] | None = None,
) -> dict:
    """年级趋势：优先读 ExamAnalysisSnapshot（W1 预计算），无快照时实时聚合。"""
    exams = await _load_exams_sorted(db, school_id, exam_ids)
    boundaries, labels = await get_segment_config(db, school_id, subject_code)
    points = []

    for exam in exams:
        snap_query = select(ExamAnalysisSnapshot).where(
            ExamAnalysisSnapshot.exam_id == exam.id,
            ExamAnalysisSnapshot.school_id == school_id,
            ExamAnalysisSnapshot.snapshot_type == "school_overview",
            ExamAnalysisSnapshot.status == "ready",
        )
        if subject_code:
            snap_query = snap_query.where(ExamAnalysisSnapshot.subject_code == subject_code)
        snap_result = await db.execute(snap_query)
        snapshot = snap_result.scalar_one_or_none()

        if snapshot and snapshot.metrics:
            m = snapshot.metrics
            points.append({
                "exam_id": exam.id,
                "exam_name": exam.name,
                "exam_date": exam.exam_date.isoformat() if exam.exam_date else None,
                "avg": m.get("avg"),
                "median": m.get("median"),
                "pass_rate": m.get("pass_rate"),
                "excellent_rate": m.get("excellent_rate"),
                "student_count": m.get("student_count", 0),
            })
            continue

        # Fallback: 实时聚合
        subjects = await _get_subjects(db, exam.id, school_id, visible_subject_codes)
        if subject_code:
            subjects = [s for s in subjects if s.code == subject_code]

        student_totals: dict[str, float] = {}
        total_max = 0.0
        for subj in subjects:
            max_by = await _get_max_by_subject(db, [subj.id], school_id)
            total_max += max_by.get(subj.id, 0.0)
            scores = await get_effective_scores(db, subj.id, school_id)
            for s in scores:
                student_totals[s["student_id"]] = student_totals.get(s["student_id"], 0) + s["effective_score"]

        values = list(student_totals.values())
        n = len(values)
        avg = round(sum(values) / n, 2) if n > 0 else 0
        segs = compute_segments(values, total_max, boundaries, labels)
        pass_rate = sum(s["count"] for s in segs[:-1]) / n if n > 0 else 0
        excellent_rate = segs[0]["count"] / n if n > 0 else 0

        points.append({
            "exam_id": exam.id,
            "exam_name": exam.name,
            "exam_date": exam.exam_date.isoformat() if exam.exam_date else None,
            "avg": avg,
            "median": round(_statistics.median(values), 2) if n > 0 else 0,
            "pass_rate": round(pass_rate, 4),
            "excellent_rate": round(excellent_rate, 4),
            "student_count": n,
        })

    return {"points": points}


async def get_class_trend(
    db: AsyncSession,
    school_id: str,
    exam_ids: list[str],
    class_id: str,
    subject_code: str | None = None,
    visible_subject_codes: list[str] | None = None,
) -> dict:
    """班级趋势：优先读 ClassExamReport（W1 预计算），无快照时实时聚合。"""
    exams = await _load_exams_sorted(db, school_id, exam_ids)
    points = []

    for exam in exams:
        # ClassExamReport 没有 subject_code 字段，只存总分口径。
        # 有 subject_code 过滤时必须跳过快照路径。
        report = None
        if not subject_code:
            report_result = await db.execute(
                select(ClassExamReport).where(
                    ClassExamReport.exam_id == exam.id,
                    ClassExamReport.school_id == school_id,
                    ClassExamReport.class_id == class_id,
                    ClassExamReport.status == "ready",
                )
            )
            report = report_result.scalar_one_or_none()

        if report:
            class_avg = report.class_avg or 0
            points.append({
                "exam_id": exam.id,
                "exam_name": exam.name,
                "exam_date": exam.exam_date.isoformat() if exam.exam_date else None,
                "class_avg": class_avg,
                "grade_avg": report.grade_avg,
                "grade_rank": report.grade_rank,
                "vs_prev": round(class_avg - points[-1]["class_avg"], 2) if points else None,
            })
            continue

        # Fallback: 实时聚合
        subjects = await _get_subjects(db, exam.id, school_id, visible_subject_codes)
        if subject_code:
            subjects = [s for s in subjects if s.code == subject_code]

        all_students: dict[str, float] = {}
        for subj in subjects:
            scores = await get_effective_scores(db, subj.id, school_id)
            for s in scores:
                all_students[s["student_id"]] = all_students.get(s["student_id"], 0) + s["effective_score"]

        student_ids = list(all_students.keys())
        student_class_map: dict[str, str] = {}
        if student_ids:
            result = await db.execute(
                select(Student.id, Student.class_id).where(Student.id.in_(student_ids))
            )
            student_class_map = {row.id: row.class_id for row in result.all()}

        class_values = [sc for sid, sc in all_students.items() if student_class_map.get(sid) == class_id]
        class_avg = round(sum(class_values) / len(class_values), 2) if class_values else 0
        all_values = list(all_students.values())
        grade_avg = round(sum(all_values) / len(all_values), 2) if all_values else 0

        class_avgs_map: dict[str, list] = {}
        for sid, score in all_students.items():
            cid = student_class_map.get(sid, "unknown")
            class_avgs_map.setdefault(cid, []).append(score)
        class_avg_sorted = sorted(
            [(cid, sum(scores) / len(scores)) for cid, scores in class_avgs_map.items()],
            key=lambda x: x[1], reverse=True,
        )
        grade_rank = next((i + 1 for i, (cid, _) in enumerate(class_avg_sorted) if cid == class_id), None)

        points.append({
            "exam_id": exam.id,
            "exam_name": exam.name,
            "exam_date": exam.exam_date.isoformat() if exam.exam_date else None,
            "class_avg": class_avg,
            "grade_avg": grade_avg,
            "grade_rank": grade_rank,
            "vs_prev": round(class_avg - points[-1]["class_avg"], 2) if points else None,
        })

    return {"class_id": class_id, "points": points}


async def get_student_trend(
    db: AsyncSession,
    school_id: str,
    exam_ids: list[str],
    student_id: str,
    subject_code: str | None = None,
    visible_subject_codes: list[str] | None = None,
) -> dict:
    """学生趋势：优先读 StudentExamSnapshot（pipeline 预计算），无快照时实时聚合。"""
    exams = await _load_exams_sorted(db, school_id, exam_ids)
    points = []

    for exam in exams:
        snap_query = select(StudentExamSnapshot).where(
            StudentExamSnapshot.exam_id == exam.id,
            StudentExamSnapshot.student_id == student_id,
            StudentExamSnapshot.school_id == school_id,
        )
        if subject_code:
            snap_query = snap_query.where(StudentExamSnapshot.subject_code == subject_code)
        else:
            snap_query = snap_query.where(StudentExamSnapshot.subject_code == "_total")
        snap_result = await db.execute(snap_query)
        snapshot = snap_result.scalar_one_or_none()

        if snapshot:
            stu_row = await db.execute(
                select(Student.class_id).where(Student.id == student_id)
            )
            stu_class = stu_row.scalar_one_or_none()
            snap_class_avg = None
            snap_grade_avg = None
            if stu_class and not subject_code:
                cr_result = await db.execute(
                    select(ClassExamReport).where(
                        ClassExamReport.exam_id == exam.id,
                        ClassExamReport.school_id == school_id,
                        ClassExamReport.class_id == stu_class,
                        ClassExamReport.status == "ready",
                    )
                )
                cr = cr_result.scalar_one_or_none()
                if cr:
                    snap_class_avg = cr.class_avg
                    snap_grade_avg = cr.grade_avg
            if snap_grade_avg is None:
                ea_query = select(ExamAnalysisSnapshot).where(
                    ExamAnalysisSnapshot.exam_id == exam.id,
                    ExamAnalysisSnapshot.school_id == school_id,
                    ExamAnalysisSnapshot.snapshot_type == "school_overview",
                    ExamAnalysisSnapshot.status == "ready",
                )
                if subject_code:
                    ea_query = ea_query.where(ExamAnalysisSnapshot.subject_code == subject_code)
                ea_result = await db.execute(ea_query)
                ea = ea_result.scalar_one_or_none()
                if ea and ea.metrics:
                    snap_grade_avg = ea.metrics.get("avg")
            points.append({
                "exam_id": exam.id,
                "exam_name": exam.name,
                "exam_date": snapshot.exam_date.isoformat() if snapshot.exam_date else (exam.exam_date.isoformat() if exam.exam_date else None),
                "score": snapshot.total_score,
                "class_rank": snapshot.class_rank,
                "grade_rank": snapshot.grade_rank,
                "class_avg": snap_class_avg,
                "grade_avg": snap_grade_avg,
            })
            continue

        # Fallback: 实时聚合
        subjects = await _get_subjects(db, exam.id, school_id, visible_subject_codes)
        if subject_code:
            subjects = [s for s in subjects if s.code == subject_code]

        all_students: dict[str, float] = {}
        for subj in subjects:
            scores = await get_effective_scores(db, subj.id, school_id)
            for s in scores:
                all_students[s["student_id"]] = all_students.get(s["student_id"], 0) + s["effective_score"]

        student_score = all_students.get(student_id)
        if student_score is None:
            continue

        ranked = sorted(all_students.values(), reverse=True)
        grade_rank = ranked.index(student_score) + 1

        result = await db.execute(select(Student.class_id).where(Student.id == student_id))
        row = result.first()
        stu_class_id = row.class_id if row else None
        class_rank = None
        class_avg = None
        if stu_class_id:
            student_ids_list = list(all_students.keys())
            if student_ids_list:
                cls_result = await db.execute(
                    select(Student.id, Student.class_id).where(Student.id.in_(student_ids_list))
                )
                cls_map = {r.id: r.class_id for r in cls_result.all()}
                class_scores = sorted(
                    [sc for sid, sc in all_students.items() if cls_map.get(sid) == stu_class_id],
                    reverse=True,
                )
                class_rank = class_scores.index(student_score) + 1 if student_score in class_scores else None
                class_avg = round(sum(class_scores) / len(class_scores), 2) if class_scores else None

        all_values = list(all_students.values())
        grade_avg = round(sum(all_values) / len(all_values), 2) if all_values else 0

        points.append({
            "exam_id": exam.id,
            "exam_name": exam.name,
            "exam_date": exam.exam_date.isoformat() if exam.exam_date else None,
            "score": student_score,
            "class_rank": class_rank,
            "grade_rank": grade_rank,
            "class_avg": class_avg,
            "grade_avg": grade_avg,
        })

    return {"student_id": student_id, "points": points}


async def _load_exams_sorted(
    db: AsyncSession, school_id: str, exam_ids: list[str],
) -> list[Exam]:
    """加载并按 exam_date 升序排列考试。"""
    result = await db.execute(
        select(Exam)
        .where(Exam.id.in_(exam_ids), Exam.school_id == school_id)
        .order_by(Exam.exam_date.asc())
    )
    exams = list(result.scalars().all())
    if len(exams) != len(exam_ids):
        found_ids = {e.id for e in exams}
        missing = [eid for eid in exam_ids if eid not in found_ids]
        raise NotFoundError(f"Exams not found: {missing}")
    return exams
