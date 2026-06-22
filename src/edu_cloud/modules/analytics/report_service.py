"""自定义分析构建器 + 跨考试对比 + PDF 导出。"""
import logging
import statistics as _statistics
from collections import defaultdict

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from edu_cloud.services.analytics_workflow import Exam
from edu_cloud.modules.analytics.service import (
    exam_summary, exam_distribution, grade_aggregates,
    subject_question_analysis, _get_subjects, _get_max_by_subject,
    _verify_exam,
)
from edu_cloud.services.effective_scores import get_effective_scores, get_effective_scores_batch
from edu_cloud.modules.analytics.segment_service import get_segment_config, compute_segments
from edu_cloud.services.analytics_workflow import Class, Student
from edu_cloud.models.agent_snapshot import ExamAnalysisSnapshot, ClassExamReport
from edu_cloud.services.analytics_workflow import StudentExamSnapshot
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


def _empty_report(exam: "Exam") -> dict:
    return {
        "exam": {"name": exam.name, "id": exam.id},
        "overview": {
            "student_count": 0, "subject_count": 0, "total_full_score": 0,
            "avg_score": None, "max_score": None, "min_score": None,
            "pass_rate": 0, "excellent_rate": 0, "full_score_count": 0,
        },
        "subjects": [], "classes": [], "students": [], "distribution": [],
        "scope": {
            "has_previous_exam": False, "subject_name": None,
            "class_name": None, "previous_exam": None,
        },
    }


async def basic_report(
    db: AsyncSession,
    *,
    exam_id: str,
    school_id: str,
    subject_id: str | None = None,
    class_id: str | None = None,
    visible_subject_codes: list[str] | None = None,
    visible_class_ids: list[str] | None = None,
) -> dict:
    """All-in-one report aggregating overview/subjects/classes/students/distribution."""
    from edu_cloud.modules.analytics.ranking_service import _find_prev_exam

    exam = await _verify_exam(db, exam_id, school_id)
    subjects = await _get_subjects(db, exam_id, school_id, visible_subject_codes, subject_id)
    if not subjects:
        return _empty_report(exam)

    subj_ids = [s.id for s in subjects]
    max_by_subject = await _get_max_by_subject(db, subj_ids, school_id)
    total_full_score = sum(max_by_subject.get(s.id, 0) for s in subjects)

    effective_class_ids = visible_class_ids
    if class_id:
        if visible_class_ids is not None and class_id not in visible_class_ids:
            return _empty_report(exam)
        effective_class_ids = [class_id]

    scores_by_subject = await get_effective_scores_batch(
        db, subj_ids, school_id, effective_class_ids,
    )

    student_subject_scores: dict[str, dict[str, float]] = defaultdict(lambda: defaultdict(float))
    student_totals: dict[str, float] = defaultdict(float)
    all_student_ids: set[str] = set()

    for subj in subjects:
        for s in scores_by_subject.get(subj.id, []):
            sid = s["student_id"]
            all_student_ids.add(sid)
            student_totals[sid] += s["effective_score"]
            student_subject_scores[sid][subj.code] += s["effective_score"]

    # --- Subject stats ---
    subject_entries = []
    for subj in subjects:
        stu_scores: dict[str, float] = defaultdict(float)
        for s in scores_by_subject.get(subj.id, []):
            stu_scores[s["student_id"]] += s["effective_score"]
        vals = list(stu_scores.values())
        full = max_by_subject.get(subj.id, 0)
        cnt = len(vals)
        avg = sum(vals) / cnt if cnt else 0
        pass_cnt = sum(1 for v in vals if full > 0 and v >= full * 0.6)
        exc_cnt = sum(1 for v in vals if full > 0 and v >= full * 0.85)
        subject_entries.append({
            "subject_id": subj.id, "subject_code": subj.code, "subject_name": subj.name,
            "full_score": full, "student_count": cnt,
            "avg_score": round(avg, 2) if cnt else None,
            "max_score": round(max(vals), 2) if vals else None,
            "min_score": round(min(vals), 2) if vals else None,
            "score_rate": round(avg / full, 4) if cnt and full > 0 else 0,
            "pass_rate": round(pass_cnt / cnt, 4) if cnt else 0,
            "excellent_rate": round(exc_cnt / cnt, 4) if cnt else 0,
        })

    # --- Student info (batch) ---
    stu_ids_list = list(student_totals.keys())
    stu_info: dict[str, dict] = {}
    if stu_ids_list:
        stu_result = await db.execute(
            select(Student.id, Student.name, Student.student_number, Student.class_id,
                   Class.name.label("class_name"))
            .outerjoin(Class, Class.id == Student.class_id)
            .where(Student.id.in_(stu_ids_list), Student.school_id == school_id)
        )
        for r in stu_result.all():
            stu_info[r.id] = {
                "name": r.name, "student_number": r.student_number,
                "class_id": r.class_id, "class_name": r.class_name,
            }

    # --- Rankings ---
    ranked = sorted(student_totals.items(), key=lambda x: x[1], reverse=True)
    grade_ranks = {sid: i + 1 for i, (sid, _) in enumerate(ranked)}
    by_class: dict[str, list[tuple[str, float]]] = defaultdict(list)
    for sid, total in ranked:
        cid = stu_info.get(sid, {}).get("class_id")
        if cid:
            by_class[cid].append((sid, total))
    class_ranks: dict[str, int] = {}
    for cls_students in by_class.values():
        for i, (sid, _) in enumerate(cls_students):
            class_ranks[sid] = i + 1

    # --- Delta (previous exam) ---
    prev_exam_id = await _find_prev_exam(db, exam_id, school_id)
    prev_exam_info = None
    prev_grade_ranks: dict[str, int] = {}
    prev_class_ranks: dict[str, int] = {}
    if prev_exam_id:
        prev_exam_obj = (await db.execute(
            select(Exam).where(Exam.id == prev_exam_id, Exam.school_id == school_id)
        )).scalar_one_or_none()
        if prev_exam_obj:
            prev_exam_info = {"name": prev_exam_obj.name}
        if subject_id:
            current_codes = [s.code for s in subjects]
            prev_subjects = await _get_subjects(
                db, prev_exam_id, school_id,
                visible_subject_codes=current_codes,
            )
        else:
            prev_subjects = await _get_subjects(db, prev_exam_id, school_id, visible_subject_codes)
        if prev_subjects:
            prev_subj_ids = [s.id for s in prev_subjects]
            prev_by_subj = await get_effective_scores_batch(db, prev_subj_ids, school_id, effective_class_ids)
            prev_totals: dict[str, float] = defaultdict(float)
            for subj in prev_subjects:
                for s in prev_by_subj.get(subj.id, []):
                    prev_totals[s["student_id"]] += s["effective_score"]
            prev_ranked = sorted(prev_totals.items(), key=lambda x: x[1], reverse=True)
            for i, (sid, _) in enumerate(prev_ranked):
                prev_grade_ranks[sid] = i + 1
            prev_by_cls: dict[str, list[tuple[str, float]]] = defaultdict(list)
            for sid, total in prev_ranked:
                cid = stu_info.get(sid, {}).get("class_id")
                if cid:
                    prev_by_cls[cid].append((sid, total))
            for cls_students in prev_by_cls.values():
                for i, (sid, _) in enumerate(cls_students):
                    prev_class_ranks[sid] = i + 1

    # --- Build student entries ---
    student_entries = []
    for sid, total in ranked:
        info = stu_info.get(sid, {})
        gr = grade_ranks[sid]
        cr = class_ranks.get(sid)
        pgr = prev_grade_ranks.get(sid)
        pcr = prev_class_ranks.get(sid)
        subj_map = {code: {"score": round(sc, 2)} for code, sc in student_subject_scores[sid].items()}
        student_entries.append({
            "student_id": sid,
            "name": info.get("name", sid),
            "student_number": info.get("student_number"),
            "class_name": info.get("class_name"),
            "total_score": round(total, 2),
            "score_rate": round(total / total_full_score, 4) if total_full_score > 0 else 0,
            "grade_rank": gr, "class_rank": cr,
            "delta_grade": (pgr - gr) if pgr is not None else None,
            "delta_class": (pcr - cr) if pcr is not None and cr is not None else None,
            "subject_scores": subj_map,
        })

    # --- Class stats ---
    class_entries = []
    for cid, cls_students in by_class.items():
        vals = [t for _, t in cls_students]
        cnt = len(vals)
        avg = sum(vals) / cnt if cnt else 0
        pass_cnt = sum(1 for v in vals if total_full_score > 0 and v >= total_full_score * 0.6)
        exc_cnt = sum(1 for v in vals if total_full_score > 0 and v >= total_full_score * 0.85)
        cname = stu_info.get(cls_students[0][0], {}).get("class_name", "") if cls_students else ""
        class_entries.append({
            "class_id": cid, "class_name": cname, "student_count": cnt,
            "avg_score": round(avg, 2) if cnt else None,
            "max_score": round(max(vals), 2) if vals else None,
            "min_score": round(min(vals), 2) if vals else None,
            "score_rate": round(avg / total_full_score, 4) if cnt and total_full_score > 0 else 0,
            "pass_rate": round(pass_cnt / cnt, 4) if cnt else 0,
            "excellent_rate": round(exc_cnt / cnt, 4) if cnt else 0,
        })
    class_entries.sort(key=lambda x: (x["avg_score"] is None, -(x["avg_score"] or 0)))
    for i, entry in enumerate(class_entries):
        entry["rank"] = i + 1

    # --- Distribution ---
    dist_data = await exam_distribution(
        db, exam_id=exam_id, school_id=school_id, subject_id=subject_id,
        visible_subject_codes=visible_subject_codes,
        visible_class_ids=effective_class_ids,
    )

    # --- Overview ---
    all_vals = list(student_totals.values())
    n = len(all_vals)
    overview_avg = sum(all_vals) / n if n else 0
    pass_n = sum(1 for v in all_vals if total_full_score > 0 and v >= total_full_score * 0.6)
    exc_n = sum(1 for v in all_vals if total_full_score > 0 and v >= total_full_score * 0.85)
    full_n = sum(1 for v in all_vals if total_full_score > 0 and abs(v - total_full_score) < 0.01)

    # --- Scope ---
    scope_subject = subjects[0].name if subject_id and subjects else None
    scope_class = None
    if class_id:
        for info in stu_info.values():
            if info.get("class_id") == class_id:
                scope_class = info.get("class_name")
                break

    return {
        "exam": {"name": exam.name, "id": exam.id},
        "overview": {
            "student_count": len(all_student_ids), "subject_count": len(subjects),
            "total_full_score": total_full_score,
            "avg_score": round(overview_avg, 2) if n else None,
            "max_score": round(max(all_vals), 2) if all_vals else None,
            "min_score": round(min(all_vals), 2) if all_vals else None,
            "pass_rate": round(pass_n / n, 4) if n else 0,
            "excellent_rate": round(exc_n / n, 4) if n else 0,
            "full_score_count": full_n,
        },
        "subjects": subject_entries,
        "classes": class_entries,
        "students": student_entries,
        "distribution": dist_data.get("intervals", []),
        "scope": {
            "has_previous_exam": prev_exam_id is not None,
            "subject_name": scope_subject, "class_name": scope_class,
            "previous_exam": prev_exam_info,
        },
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
