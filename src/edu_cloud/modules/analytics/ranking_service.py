"""学生排名 + 进退步 + 临界生筛选 + 箱线图 + 知识点热力图。"""
import logging
import statistics
from collections import Counter, defaultdict

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from edu_cloud.modules.exam.models import Exam, Subject, Question
from edu_cloud.modules.scan.models import StudentAnswer
from edu_cloud.modules.grading.models import GradingResult
from edu_cloud.modules.student.models import Class, Student
from edu_cloud.modules.knowledge.models import QuestionKnowledgePoint
from edu_cloud.modules.knowledge_tree.models import ConceptGraphNode

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

    from edu_cloud.services.effective_scores import get_effective_scores_batch
    student_totals: dict[str, float] = defaultdict(float)
    scores_by_subject = await get_effective_scores_batch(db, subj_ids, school_id, visible_class_ids)
    for sid in subj_ids:
        for s in scores_by_subject.get(sid, []):
            student_totals[s["student_id"]] += s["effective_score"]

    # 获取学生信息
    stu_result = await db.execute(
        select(Student.id, Student.name, Student.class_id, Class.name.label("class_name"))
        .outerjoin(Class, Class.id == Student.class_id)
        .where(Student.school_id == school_id)
    )
    stu_map = {
        r.id: {"name": r.name, "class_id": r.class_id, "class_name": r.class_name}
        for r in stu_result.all()
    }

    result = []
    for sid, total in student_totals.items():
        info = stu_map.get(sid, {"name": sid, "class_id": None, "class_name": None})
        result.append({
            "student_id": sid,
            "name": info["name"],
            "class_id": info["class_id"],
            "class_name": info["class_name"],
            "score": total,
        })

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
    if class_id:
        if visible_class_ids is not None and class_id not in visible_class_ids:
            return {"students": []}
        effective_class_ids = [class_id]
    else:
        effective_class_ids = visible_class_ids
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
            "class_id": s.get("class_id"),
            "class_name": s.get("class_name"),
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
    from edu_cloud.services.effective_scores import get_effective_scores_batch as _batch_eff

    if class_id:
        if visible_class_ids is not None and class_id not in visible_class_ids:
            return {"near_pass": [], "near_excellent": []}
        effective_class_ids = [class_id]
    else:
        effective_class_ids = visible_class_ids
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

    eff_by_subject = await _batch_eff(db, subj_ids, school_id, effective_class_ids)
    for subj in subjects:
        for s in eff_by_subject.get(subj.id, []):
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


async def class_knowledge(
    db: AsyncSession, *, exam_id: str, school_id: str,
    subject_id: str | None = None,
    visible_subject_codes: list[str] | None = None,
    visible_class_ids: list[str] | None = None,
) -> dict:
    """班级×知识点 掌握率热力图数据。"""
    from edu_cloud.modules.exam.models import Subject, Question
    from edu_cloud.services.effective_scores import get_effective_scores_batch as _batch_scores

    subj_q = select(Subject).where(Subject.exam_id == exam_id, Subject.school_id == school_id)
    if subject_id:
        subj_q = subj_q.where(Subject.id == subject_id)
    if visible_subject_codes is not None:
        subj_q = subj_q.where(Subject.code.in_(visible_subject_codes))
    subjects = list((await db.execute(subj_q)).scalars().all())
    if not subjects:
        return {"knowledge_points": [], "classes": []}

    subj_ids = [s.id for s in subjects]

    # 获取题目 max_score 映射
    q_result = await db.execute(
        select(Question.id, Question.max_score)
        .where(Question.subject_id.in_(subj_ids), Question.school_id == school_id)
    )
    q_max: dict[str, float] = {}
    questions = q_result.all()
    for q in questions:
        q_max[q.id] = q.max_score

    # 从 QKP 关联表构建题目→概念映射
    q_ids = list(q_max.keys())
    kp_links_result = await db.execute(
        select(QuestionKnowledgePoint.question_id,
               ConceptGraphNode.id, ConceptGraphNode.name)
        .join(ConceptGraphNode, ConceptGraphNode.id == QuestionKnowledgePoint.concept_id)
        .where(QuestionKnowledgePoint.question_id.in_(q_ids))
    )
    q_concept_map: dict[str, list[tuple[str, str]]] = {}
    all_kps: set[str] = set()
    for q_id, concept_id, concept_name in kp_links_result.all():
        q_concept_map.setdefault(q_id, []).append((concept_id, concept_name))
        all_kps.add(concept_id)

    if not all_kps:
        return {"knowledge_points": [], "classes": []}

    # 概念 id→name 映射（用于最终输出）
    concept_name_map: dict[str, str] = {}
    for concepts in q_concept_map.values():
        for concept_id, concept_name in concepts:
            concept_name_map[concept_id] = concept_name

    # 聚合每个学生每个知识点的得分率
    scores_by_subject = await _batch_scores(db, subj_ids, school_id, visible_class_ids)
    student_kp_scores: dict[str, dict[str, list[float]]] = defaultdict(lambda: defaultdict(list))
    for subj in subjects:
        for s in scores_by_subject.get(subj.id, []):
            concepts = q_concept_map.get(s["question_id"], [])
            max_s = q_max.get(s["question_id"], 1)
            rate = s["effective_score"] / max_s if max_s > 0 else 0
            for concept_id, _ in concepts:
                student_kp_scores[s["student_id"]][concept_id].append(rate)

    # 学生→班级映射
    all_sids = list(student_kp_scores.keys())
    stu_result = await db.execute(
        select(Student.id, Student.class_id).where(Student.id.in_(all_sids))
    )
    stu_class = {r.id: r.class_id for r in stu_result.all()}

    # 按班聚合
    class_kp_rates: dict[str, dict[str, list[float]]] = defaultdict(lambda: defaultdict(list))
    for sid, kp_data in student_kp_scores.items():
        cid = stu_class.get(sid)
        if not cid:
            continue
        for kp, rates in kp_data.items():
            avg_rate = sum(rates) / len(rates) if rates else 0
            class_kp_rates[cid][kp].append(avg_rate)

    # 班级名
    class_ids = list(class_kp_rates.keys())
    cls_result = await db.execute(select(Class.id, Class.name).where(Class.id.in_(class_ids)))
    cls_map = {r.id: r.name for r in cls_result.all()}

    kp_list = sorted(all_kps)
    classes = []
    for cid, kp_data in class_kp_rates.items():
        mastery = []
        for concept_id in kp_list:
            rates = kp_data.get(concept_id, [])
            avg = round(sum(rates) / len(rates), 4) if rates else 0
            mastery.append({"kp_id": concept_id, "name": concept_name_map.get(concept_id, concept_id), "rate": avg})
        classes.append({"class_id": cid, "name": cls_map.get(cid, cid), "mastery": mastery})
    classes.sort(key=lambda x: x["name"])
    return {"knowledge_points": kp_list, "classes": classes}


async def class_error_patterns(
    db: AsyncSession, *, exam_id: str, school_id: str,
    subject_id: str | None = None,
    class_id: str | None = None,
    visible_subject_codes: list[str] | None = None,
    visible_class_ids: list[str] | None = None,
) -> dict:
    """班级错误模式对比。"""
    from edu_cloud.modules.analytics.insights_service import _classify_error

    # 需要按班拆分 — 重新查询带 class_id 信息的 GradingResult
    subj_q = select(Subject.id).where(Subject.exam_id == exam_id, Subject.school_id == school_id)
    if subject_id:
        subj_q = subj_q.where(Subject.id == subject_id)
    if visible_subject_codes is not None:
        subj_q = subj_q.where(Subject.code.in_(visible_subject_codes))
    subj_ids = [r[0] for r in (await db.execute(subj_q)).all()]
    if not subj_ids:
        return {"error_types": [], "classes": []}

    stmt = (
        select(
            StudentAnswer.student_id,
            Student.class_id,
            GradingResult.ai_raw_response,
        )
        .select_from(GradingResult)
        .join(StudentAnswer, StudentAnswer.id == GradingResult.answer_id)
        .outerjoin(Student, Student.id == StudentAnswer.student_id)
        .where(
            StudentAnswer.subject_id.in_(subj_ids),
            GradingResult.school_id == school_id,
            GradingResult.ai_raw_response.isnot(None),
        )
    )

    rows = (await db.execute(stmt)).all()
    from edu_cloud.modules.analytics.identity import resolve_student_identities
    identities = await resolve_student_identities(
        db, school_id=school_id, raw_student_ids=[row.student_id for row in rows],
    )
    # Narrow to single class when class_id is specified
    if class_id:
        if visible_class_ids is not None and class_id not in visible_class_ids:
            return {"error_types": [], "classes": []}
        effective_class_ids = [class_id]
    else:
        effective_class_ids = visible_class_ids
    visible_set = set(effective_class_ids) if effective_class_ids is not None else None

    class_errors: dict[str, Counter] = defaultdict(Counter)
    all_types: set[str] = set()
    for row in rows:
        identity = identities.get(row.student_id)
        cid = row.class_id or (identity.class_id if identity else None)
        if not cid or (visible_set is not None and cid not in visible_set):
            continue
        raw = row.ai_raw_response
        if not isinstance(raw, dict):
            continue
        for detail in raw.get("details", []):
            if not isinstance(detail, dict):
                continue
            for blank in detail.get("blanks", []):
                if not isinstance(blank, dict):
                    continue
                if blank.get("correct") is False and blank.get("reason"):
                    cause = _classify_error(blank["reason"])
                    class_errors[cid][cause] += 1
                    all_types.add(cause)

    # 班级名
    class_ids = list(class_errors.keys())
    if not class_ids:
        return {"error_types": [], "classes": []}
    cls_result = await db.execute(select(Class.id, Class.name).where(Class.id.in_(class_ids)))
    cls_map = {r.id: r.name for r in cls_result.all()}

    error_types = sorted(all_types)
    classes = []
    for cid, counter in class_errors.items():
        total = sum(counter.values())
        dist = {t: round(counter.get(t, 0) / total, 4) if total > 0 else 0 for t in error_types}
        classes.append({"class_id": cid, "name": cls_map.get(cid, cid), "distribution": dist})
    classes.sort(key=lambda x: x["name"])
    return {"error_types": error_types, "classes": classes}
