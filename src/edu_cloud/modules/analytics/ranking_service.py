"""学生排名 + 进退步 + 临界生筛选 + 箱线图 + 知识点热力图。"""
import logging
import statistics
from collections import defaultdict

from sqlalchemy import select, func, and_
from sqlalchemy.ext.asyncio import AsyncSession

from edu_cloud.modules.exam.models import Exam, Subject, Question
from edu_cloud.modules.scan.models import StudentAnswer
from edu_cloud.modules.grading.models import GradingResult
from edu_cloud.modules.student.models import Class, Student
from edu_cloud.services.exceptions import NotFoundError

logger = logging.getLogger(__name__)


async def _get_student_scores(
    db: AsyncSession, exam_id: str, school_id: str,
    subject_id: str | None = None,
    visible_class_ids: list[str] | None = None,
    visible_subject_codes: list[str] | None = None,
) -> list[dict]:
    """聚合每个学生在某次考试的总分。

    F002 修复：增加 visible_subject_codes 过滤，防止受限角色看到超范围科目数据。
    """
    subj_q = select(Subject.id).where(Subject.exam_id == exam_id, Subject.school_id == school_id)
    if subject_id:
        subj_q = subj_q.where(Subject.id == subject_id)
    if visible_subject_codes is not None:
        subj_q = subj_q.where(Subject.code.in_(visible_subject_codes))
    subj_ids = [r[0] for r in (await db.execute(subj_q)).all()]
    if not subj_ids:
        return []

    from edu_cloud.modules.analytics import get_effective_scores
    student_totals: dict[str, float] = defaultdict(float)
    for sid in subj_ids:
        scores = await get_effective_scores(db, sid, school_id, visible_class_ids)
        for s in scores:
            student_totals[s["student_id"]] += s["effective_score"]

    # 获取学生信息
    stu_result = await db.execute(
        select(Student.id, Student.name, Student.class_id)
        .where(Student.school_id == school_id)
    )
    stu_map = {r.id: {"name": r.name, "class_id": r.class_id} for r in stu_result.all()}

    result = []
    for sid, total in student_totals.items():
        info = stu_map.get(sid, {"name": sid, "class_id": None})
        result.append({"student_id": sid, "name": info["name"], "class_id": info["class_id"], "score": total})

    result.sort(key=lambda x: x["score"], reverse=True)
    # 年级排名
    for i, r in enumerate(result):
        r["grade_rank"] = i + 1
        r["grade_size"] = len(result)
    # 班级排名
    by_class: dict[str, list] = defaultdict(list)
    for r in result:
        by_class[r["class_id"]].append(r)
    for cls_students in by_class.values():
        for i, r in enumerate(cls_students):
            r["class_rank"] = i + 1
            r["class_size"] = len(cls_students)

    return result


async def _find_prev_exam(db: AsyncSession, exam_id: str, school_id: str) -> str | None:
    """找到同校上一次考试（按 exam_date 或 created_at 倒序）。"""
    """F005 修复：限同年级——通过 Subject 关联找到当前考试的年级（从 Student→Class→grade），
    然后只在同年级考试中找上一次。"""
    current = (await db.execute(
        select(Exam).where(Exam.id == exam_id, Exam.school_id == school_id)
    )).scalar_one_or_none()
    if not current:
        return None

    # 找当前考试的年级（通过参与学生的班级）
    grade_result = await db.execute(
        select(Class.grade).distinct()
        .select_from(StudentAnswer)
        .join(Student, Student.id == StudentAnswer.student_id)
        .join(Class, Class.id == Student.class_id)
        .where(StudentAnswer.exam_id == exam_id)
        .limit(1)
    )
    grade = grade_result.scalar_one_or_none()

    order_col = Exam.exam_date if current.exam_date else Exam.created_at
    prev_q = (
        select(Exam.id)
        .where(Exam.school_id == school_id, Exam.status == "completed", Exam.id != exam_id)
        .where(order_col < (current.exam_date or current.created_at))
        .order_by(order_col.desc())
        .limit(1)
    )
    # 限同年级：只找包含同年级学生的考试
    if grade:
        prev_q = prev_q.where(
            Exam.id.in_(
                select(StudentAnswer.exam_id).distinct()
                .join(Student, Student.id == StudentAnswer.student_id)
                .join(Class, Class.id == Student.class_id)
                .where(Class.grade == grade)
            )
        )
    prev = (await db.execute(prev_q)).scalar_one_or_none()
    return prev


async def student_rankings(
    db: AsyncSession, *, exam_id: str, school_id: str,
    subject_id: str | None = None,
    class_id: str | None = None,
    visible_subject_codes: list[str] | None = None,
    visible_class_ids: list[str] | None = None,
) -> dict:
    """学生排名 + 进退步 delta。"""
    effective_class_ids = [class_id] if class_id else visible_class_ids
    current = await _get_student_scores(db, exam_id, school_id, subject_id, effective_class_ids, visible_subject_codes)
    if not current:
        return {"students": []}

    # 上次考试排名
    prev_exam_id = await _find_prev_exam(db, exam_id, school_id)
    prev_map: dict[str, dict] = {}
    if prev_exam_id:
        prev_scores = await _get_student_scores(db, prev_exam_id, school_id, subject_id, effective_class_ids, visible_subject_codes)
        for p in prev_scores:
            prev_map[p["student_id"]] = p

    students = []
    for s in current:
        prev = prev_map.get(s["student_id"])
        students.append({
            "student_id": s["student_id"],
            "name": s["name"],
            "score": round(s["score"], 2),
            "class_rank": s.get("class_rank"),
            "grade_rank": s["grade_rank"],
            "prev_class_rank": prev["class_rank"] if prev else None,
            "prev_grade_rank": prev["grade_rank"] if prev else None,
            "delta_class": (prev["class_rank"] - s["class_rank"]) if prev and prev.get("class_rank") else None,
            "delta_grade": (prev["grade_rank"] - s["grade_rank"]) if prev else None,
        })

    return {"students": students}


async def critical_students(
    db: AsyncSession, *, exam_id: str, school_id: str,
    subject_id: str | None = None,
    class_id: str | None = None,
    threshold: int = 3,
    visible_subject_codes: list[str] | None = None,
    visible_class_ids: list[str] | None = None,
) -> dict:
    """临界生筛选：差 N 分及格/优秀。F005 修复：返回 worst_question。"""
    from edu_cloud.modules.analytics.segment_service import get_segment_config
    from edu_cloud.modules.analytics.service import _get_max_by_subject, _get_subjects
    from edu_cloud.modules.analytics import get_effective_scores as _get_eff

    effective_class_ids = [class_id] if class_id else visible_class_ids
    scores = await _get_student_scores(db, exam_id, school_id, subject_id, effective_class_ids, visible_subject_codes)
    if not scores:
        return {"near_pass": [], "near_excellent": []}

    # 获取满分和分数段
    subjects = await _get_subjects(db, exam_id, school_id, visible_subject_codes, subject_id)
    subj_ids = [s.id for s in subjects]
    max_by_subject = await _get_max_by_subject(db, subj_ids, school_id)
    total_max = sum(max_by_subject.values())

    subject_code = subjects[0].code if len(subjects) == 1 else None
    boundaries, labels = await get_segment_config(db, school_id, subject_code)

    # 及格线和优秀线（按百分比×满分）
    pass_line = total_max * (boundaries[-1] / 100) if boundaries else total_max * 0.6
    excellent_line = total_max * (boundaries[0] / 100) if boundaries else total_max * 0.85

    # F005: 预计算每个学生丢分最多的题目
    student_worst: dict[str, dict] = {}
    q_meta_result = await db.execute(
        select(Question.id, Question.name, Question.max_score)
        .where(Question.subject_id.in_(subj_ids), Question.school_id == school_id)
    )
    q_meta = {r.id: {"name": r.name, "max_score": r.max_score} for r in q_meta_result.all()}

    for subj in subjects:
        eff_scores = await _get_eff(db, subj.id, school_id, effective_class_ids)
        for s in eff_scores:
            sid = s["student_id"]
            loss = s["max_score"] - s["effective_score"]
            if loss > 0:
                prev = student_worst.get(sid)
                if prev is None or loss > prev["loss"]:
                    meta = q_meta.get(s["question_id"], {"name": s["question_id"], "max_score": s["max_score"]})
                    student_worst[sid] = {
                        "question_name": meta["name"],
                        "score": round(s["effective_score"], 2),
                        "max_score": round(s["max_score"], 2),
                        "loss": round(loss, 2),
                    }

    near_pass = []
    near_excellent = []
    for s in scores:
        gap_pass = pass_line - s["score"]
        gap_excellent = excellent_line - s["score"]
        worst = student_worst.get(s["student_id"])
        if 0 < gap_pass <= threshold:
            near_pass.append({
                "student_id": s["student_id"], "name": s["name"],
                "score": round(s["score"], 2), "gap": round(gap_pass, 2),
                "worst_question": worst,
            })
        if 0 < gap_excellent <= threshold:
            near_excellent.append({
                "student_id": s["student_id"], "name": s["name"],
                "score": round(s["score"], 2), "gap": round(gap_excellent, 2),
                "worst_question": worst,
            })

    near_pass.sort(key=lambda x: x["gap"])
    near_excellent.sort(key=lambda x: x["gap"])
    return {"near_pass": near_pass, "near_excellent": near_excellent}


async def class_boxplot(
    db: AsyncSession, *, exam_id: str, school_id: str,
    subject_id: str | None = None,
    visible_subject_codes: list[str] | None = None,
    visible_class_ids: list[str] | None = None,
) -> dict:
    """各班分数箱线图数据。"""
    scores = await _get_student_scores(db, exam_id, school_id, subject_id, visible_class_ids, visible_subject_codes)
    by_class: dict[str, list[float]] = defaultdict(list)
    for s in scores:
        if s["class_id"]:
            by_class[s["class_id"]].append(s["score"])

    # 获取班级名
    class_ids = list(by_class.keys())
    if not class_ids:
        return {"classes": []}
    cls_result = await db.execute(
        select(Class.id, Class.name).where(Class.id.in_(class_ids))
    )
    cls_map = {r.id: r.name for r in cls_result.all()}

    classes = []
    for cid, vals in by_class.items():
        vals.sort()
        n = len(vals)
        classes.append({
            "class_id": cid,
            "name": cls_map.get(cid, cid),
            "count": n,
            "min": round(vals[0], 2),
            "max": round(vals[-1], 2),
            "median": round(statistics.median(vals), 2),
            "p25": round(vals[n * 25 // 100], 2) if n >= 4 else round(vals[0], 2),
            "p75": round(vals[n * 75 // 100], 2) if n >= 4 else round(vals[-1], 2),
        })
    classes.sort(key=lambda x: x["name"])
    return {"classes": classes}
