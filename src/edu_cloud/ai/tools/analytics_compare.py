"""对比聚合工具（3 个）。L2_analytics 类别。"""
from edu_cloud.ai.registry import tools
from edu_cloud.ai.tool_context import ToolContext, ToolResult


@tools.register(
    name="compare_classes",
    description="多班级成绩对比。返回各班平均分、最高分、最低分。支持 exam_subject_id 单参数替代 exam_id+subject_id。",
    category="L2_analytics",
    module_code="exam",
    domain="analytics",
    allowed_roles=["platform_admin", "academic_director", "grade_leader"],
    risk_level="low",
    is_read_only=True,
    sensitivity="school",
    parameters={
        "type": "object",
        "properties": {
            "exam_id": {"type": "string", "description": "考试 ID（与 exam_subject_id 二选一）"},
            "class_ids": {"type": "array", "items": {"type": "string"}, "description": "班级 ID 列表"},
            "subject_id": {"type": "string", "description": "可选，科目 ID"},
            "exam_subject_id": {"type": "string", "description": "科目 ID，自动解析 exam_id（与 exam_id 二选一）"},
        },
        "required": ["class_ids"],
    },
)
async def compare_classes(input: dict, ctx: ToolContext) -> ToolResult:
    exam_id = input.get("exam_id")
    class_ids = input.get("class_ids") or []
    subject_id = input.get("subject_id")
    exam_subject_id = input.get("exam_subject_id")
    try:
        from sqlalchemy import select
        from edu_cloud.modules.exam.models import Subject
        from edu_cloud.modules.analytics.service import get_effective_scores

        if exam_subject_id and not exam_id:
            from edu_cloud.modules.analytics.service import resolve_subject_to_exam
            exam_id, _ = await resolve_subject_to_exam(ctx.db, exam_subject_id, ctx.school_id)
            subject_id = exam_subject_id
        if not exam_id:
            return ToolResult(success=False, error="需要提供 exam_id 或 exam_subject_id")
        allowed_ids = class_ids
        filtered_out = []
        if ctx.class_ids is not None:
            allowed_ids = [c for c in class_ids if c in ctx.class_ids]
            filtered_out = [c for c in class_ids if c not in ctx.class_ids]

        subj_query = select(Subject).where(Subject.exam_id == exam_id, Subject.school_id == ctx.school_id)
        if subject_id:
            subj_query = subj_query.where(Subject.id == subject_id)
        if ctx.subject_codes is not None:
            subj_query = subj_query.where(Subject.code.in_(ctx.subject_codes))
        subjects = (await ctx.db.execute(subj_query)).scalars().all()

        comparisons = []
        for cid in allowed_ids:
            student_totals: dict[str, float] = {}
            for subj in subjects:
                scores = await get_effective_scores(ctx.db, subj.id, ctx.school_id, [cid])
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

        data = {"exam_id": exam_id, "comparisons": comparisons}
        if filtered_out:
            data["warning"] = f"以下班级无权访问，已从对比中排除: {filtered_out}"
        return ToolResult(success=True, data=data)
    except Exception as e:
        return ToolResult(success=False, error=str(e))


@tools.register(
    name="rank_students",
    description="学生排名表。可按科目、班级过滤，指定 top_n。支持 exam_subject_id 单参数替代 exam_id+subject_id。",
    category="L2_analytics",
    module_code="exam",
    domain="analytics",
    allowed_roles=["platform_admin", "academic_director", "grade_leader"],
    risk_level="low",
    is_read_only=True,
    sensitivity="school",
    parameters={
        "type": "object",
        "properties": {
            "exam_id": {"type": "string", "description": "考试 ID（与 exam_subject_id 二选一）"},
            "subject_id": {"type": "string", "description": "可选，科目 ID"},
            "exam_subject_id": {"type": "string", "description": "科目 ID，自动解析 exam_id（与 exam_id 二选一）"},
            "class_id": {"type": "string", "description": "可选，班级 ID"},
            "top_n": {"type": "integer", "description": "可选，返回前 N 名（默认 20）"},
        },
        "required": [],
    },
)
async def rank_students(input: dict, ctx: ToolContext) -> ToolResult:
    exam_id = input.get("exam_id")
    subject_id = input.get("subject_id")
    exam_subject_id = input.get("exam_subject_id")
    class_id = input.get("class_id")
    top_n = input.get("top_n", 20)
    try:
        if exam_subject_id and not exam_id:
            from edu_cloud.modules.analytics.service import resolve_subject_to_exam
            exam_id, _ = await resolve_subject_to_exam(ctx.db, exam_subject_id, ctx.school_id)
            subject_id = exam_subject_id
        if not exam_id:
            return ToolResult(success=False, error="需要提供 exam_id 或 exam_subject_id")
        if ctx.class_ids is not None and class_id and class_id not in ctx.class_ids:
            return ToolResult(success=False, error="无权访问该班级")

        from sqlalchemy import select
        from edu_cloud.modules.exam.models import Subject
        from edu_cloud.modules.student.models import Student
        from edu_cloud.modules.analytics.service import get_effective_scores

        scope_classes = [class_id] if class_id else ctx.class_ids

        subj_query = select(Subject).where(Subject.exam_id == exam_id, Subject.school_id == ctx.school_id)
        if subject_id:
            subj_query = subj_query.where(Subject.id == subject_id)
        if ctx.subject_codes is not None:
            subj_query = subj_query.where(Subject.code.in_(ctx.subject_codes))
        subjects = (await ctx.db.execute(subj_query)).scalars().all()

        student_totals: dict[str, float] = {}
        for subj in subjects:
            scores = await get_effective_scores(ctx.db, subj.id, ctx.school_id, scope_classes)
            for s in scores:
                student_totals[s["student_id"]] = student_totals.get(s["student_id"], 0) + s["effective_score"]

        ranked = sorted(student_totals.items(), key=lambda x: x[1], reverse=True)[:top_n]

        student_ids = [sid for sid, _ in ranked]
        if student_ids:
            students_result = await ctx.db.execute(
                select(Student).where(Student.id.in_(student_ids), Student.school_id == ctx.school_id)
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
        return ToolResult(success=True, data={"ranking": results})
    except Exception as e:
        return ToolResult(success=False, error=str(e))


@tools.register(
    name="get_grade_aggregates",
    description="获取年级聚合统计（均分/中位数/标准差）。不含个体数据。组 < 5 人不返回统计。支持 exam_subject_id 单参数。",
    category="L2_analytics",
    module_code="exam",
    domain="analytics",
    allowed_roles=["platform_admin", "academic_director", "grade_leader"],
    risk_level="low",
    is_read_only=True,
    sensitivity="school",
    parameters={
        "type": "object",
        "properties": {
            "exam_id": {"type": "string", "description": "考试 ID（与 exam_subject_id 二选一）"},
            "subject_id": {"type": "string", "description": "可选，科目 ID"},
            "exam_subject_id": {"type": "string", "description": "科目 ID，自动解析 exam_id（与 exam_id 二选一）"},
        },
        "required": [],
    },
)
async def get_grade_aggregates(input: dict, ctx: ToolContext) -> ToolResult:
    exam_id = input.get("exam_id")
    subject_id = input.get("subject_id")
    exam_subject_id = input.get("exam_subject_id")
    try:
        if exam_subject_id and not exam_id:
            from edu_cloud.modules.analytics.service import resolve_subject_to_exam
            exam_id, _ = await resolve_subject_to_exam(ctx.db, exam_subject_id, ctx.school_id)
            subject_id = exam_subject_id
        if not exam_id:
            return ToolResult(success=False, error="需要提供 exam_id 或 exam_subject_id")
        import statistics as stats_mod
        from sqlalchemy import select
        from edu_cloud.modules.exam.models import Subject
        from edu_cloud.modules.analytics.service import get_effective_scores

        subj_query = select(Subject).where(Subject.exam_id == exam_id, Subject.school_id == ctx.school_id)
        if subject_id:
            subj_query = subj_query.where(Subject.id == subject_id)
        if ctx.subject_codes is not None:
            subj_query = subj_query.where(Subject.code.in_(ctx.subject_codes))
        subjects = (await ctx.db.execute(subj_query)).scalars().all()

        student_totals: dict[str, float] = {}
        for subj in subjects:
            scores = await get_effective_scores(ctx.db, subj.id, ctx.school_id)
            for s in scores:
                student_totals[s["student_id"]] = student_totals.get(s["student_id"], 0) + s["effective_score"]

        values = list(student_totals.values())
        K_ANONYMITY = 5
        if len(values) < K_ANONYMITY:
            return ToolResult(success=False, error=f"人数不足 {K_ANONYMITY}，不返回聚合统计")

        return ToolResult(success=True, data={
            "exam_id": exam_id,
            "count": len(values),
            "avg": round(sum(values) / len(values), 2),
            "median": round(stats_mod.median(values), 2),
            "stdev": round(stats_mod.stdev(values), 2) if len(values) > 1 else 0,
            "max": max(values),
            "min": min(values),
        })
    except Exception as e:
        return ToolResult(success=False, error=str(e))
