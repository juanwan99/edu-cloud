"""对比聚合工具（3 个）。L2_analytics 类别。"""
from edu_cloud.ai.registry import tools


@tools.register(
    name="compare_classes",
    description="多班级成绩对比。返回各班平均分、最高分、最低分。",
    category="L2_analytics",
    module_code="exam",
    domain="analytics",
    allowed_roles=["platform_admin", "academic_director", "grade_leader"],
    risk_level="low",
    parameters={
        "type": "object",
        "properties": {
            "exam_id": {"type": "string", "description": "考试 ID"},
            "class_ids": {"type": "array", "items": {"type": "string"}, "description": "班级 ID 列表"},
            "subject_id": {"type": "string", "description": "可选，科目 ID"},
        },
        "required": ["exam_id", "class_ids"],
    },
)
async def compare_classes(
    exam_id: str,
    class_ids: list[str],
    subject_id: str | None = None,
    _school_id: str = "",
    _visible_classes: list[str] | None = None,
    _visible_subjects: list[str] | None = None,
    _db=None,
) -> dict:
    from sqlalchemy import select
    from edu_cloud.modules.exam.models import Subject
    from edu_cloud.modules.analytics.service import get_effective_scores

    allowed_ids = class_ids
    filtered_out = []
    if _visible_classes is not None:
        allowed_ids = [c for c in class_ids if c in _visible_classes]
        filtered_out = [c for c in class_ids if c not in _visible_classes]

    subj_query = select(Subject).where(Subject.exam_id == exam_id, Subject.school_id == _school_id)
    if subject_id:
        subj_query = subj_query.where(Subject.id == subject_id)
    if _visible_subjects is not None:
        subj_query = subj_query.where(Subject.code.in_(_visible_subjects))
    subjects = (await _db.execute(subj_query)).scalars().all()

    comparisons = []
    for cid in allowed_ids:
        student_totals: dict[str, float] = {}
        for subj in subjects:
            scores = await get_effective_scores(_db, subj.id, _school_id, [cid])
            for s in scores:
                student_totals[s["student_id"]] = student_totals.get(s["student_id"], 0) + s["effective_score"]

        values = list(student_totals.values())
        if values:
            comparisons.append({
                "class_id": cid,
                "count": len(values),
                "avg": round(sum(values) / len(values), 2),
                "max": max(values),
                "min": min(values),
            })
        else:
            comparisons.append({"class_id": cid, "count": 0, "avg": None, "max": None, "min": None})

    result = {"exam_id": exam_id, "comparisons": comparisons}
    if filtered_out:
        result["warning"] = f"以下班级无权访问，已从对比中排除: {filtered_out}"
    return result


@tools.register(
    name="rank_students",
    description="学生排名表。可按科目、班级过滤，指定 top_n。",
    category="L2_analytics",
    module_code="exam",
    domain="analytics",
    allowed_roles=["platform_admin", "academic_director", "grade_leader"],
    risk_level="low",
    parameters={
        "type": "object",
        "properties": {
            "exam_id": {"type": "string", "description": "考试 ID"},
            "subject_id": {"type": "string", "description": "可选，科目 ID"},
            "class_id": {"type": "string", "description": "可选，班级 ID"},
            "top_n": {"type": "integer", "description": "可选，返回前 N 名（默认 20）"},
        },
        "required": ["exam_id"],
    },
)
async def rank_students(
    exam_id: str,
    subject_id: str | None = None,
    class_id: str | None = None,
    top_n: int = 20,
    _school_id: str = "",
    _visible_classes: list[str] | None = None,
    _visible_subjects: list[str] | None = None,
    _db=None,
) -> dict:
    if _visible_classes is not None and class_id and class_id not in _visible_classes:
        return {"error": "无权访问该班级"}

    from sqlalchemy import select
    from edu_cloud.modules.exam.models import Subject
    from edu_cloud.modules.student.models import Student
    from edu_cloud.modules.analytics.service import get_effective_scores

    scope_classes = [class_id] if class_id else _visible_classes

    subj_query = select(Subject).where(Subject.exam_id == exam_id, Subject.school_id == _school_id)
    if subject_id:
        subj_query = subj_query.where(Subject.id == subject_id)
    if _visible_subjects is not None:
        subj_query = subj_query.where(Subject.code.in_(_visible_subjects))
    subjects = (await _db.execute(subj_query)).scalars().all()

    student_totals: dict[str, float] = {}
    for subj in subjects:
        scores = await get_effective_scores(_db, subj.id, _school_id, scope_classes)
        for s in scores:
            student_totals[s["student_id"]] = student_totals.get(s["student_id"], 0) + s["effective_score"]

    ranked = sorted(student_totals.items(), key=lambda x: x[1], reverse=True)[:top_n]

    student_ids = [sid for sid, _ in ranked]
    if student_ids:
        students_result = await _db.execute(
            select(Student).where(Student.id.in_(student_ids), Student.school_id == _school_id)
        )
        students = {s.id: s for s in students_result.scalars().all()}
    else:
        students = {}

    results = []
    for rank, (sid, total) in enumerate(ranked, 1):
        st = students.get(sid)
        results.append({
            "rank": rank,
            "student_id": sid,
            "student_name": st.name if st else "",
            "total_score": total,
        })
    return {"ranking": results}


@tools.register(
    name="get_grade_aggregates",
    description="获取年级聚合统计（均分/中位数/标准差）。不含个体数据。组 < 5 人不返回统计。",
    category="L2_analytics",
    module_code="exam",
    domain="analytics",
    allowed_roles=["platform_admin", "academic_director", "grade_leader"],
    risk_level="low",
    parameters={
        "type": "object",
        "properties": {
            "exam_id": {"type": "string", "description": "考试 ID"},
            "subject_id": {"type": "string", "description": "可选，科目 ID"},
        },
        "required": ["exam_id"],
    },
)
async def get_grade_aggregates(
    exam_id: str,
    subject_id: str | None = None,
    _school_id: str = "",
    _visible_subjects: list[str] | None = None,
    _db=None,
) -> dict:
    import statistics as stats_mod
    from sqlalchemy import select
    from edu_cloud.modules.exam.models import Subject
    from edu_cloud.modules.analytics.service import get_effective_scores

    subj_query = select(Subject).where(Subject.exam_id == exam_id, Subject.school_id == _school_id)
    if subject_id:
        subj_query = subj_query.where(Subject.id == subject_id)
    if _visible_subjects is not None:
        subj_query = subj_query.where(Subject.code.in_(_visible_subjects))
    subjects = (await _db.execute(subj_query)).scalars().all()

    student_totals: dict[str, float] = {}
    for subj in subjects:
        scores = await get_effective_scores(_db, subj.id, _school_id)
        for s in scores:
            student_totals[s["student_id"]] = student_totals.get(s["student_id"], 0) + s["effective_score"]

    values = list(student_totals.values())
    K_ANONYMITY = 5
    if len(values) < K_ANONYMITY:
        return {"exam_id": exam_id, "error": f"人数不足 {K_ANONYMITY}，不返回聚合统计"}

    return {
        "exam_id": exam_id,
        "count": len(values),
        "avg": round(sum(values) / len(values), 2),
        "median": round(stats_mod.median(values), 2),
        "stdev": round(stats_mod.stdev(values), 2) if len(values) > 1 else 0,
        "max": max(values),
        "min": min(values),
    }
