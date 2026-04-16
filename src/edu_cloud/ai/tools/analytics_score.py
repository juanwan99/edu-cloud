"""成绩查询工具（5 个）。L2_analytics 类别。"""
from edu_cloud.ai.registry import tools
from edu_cloud.ai.tool_context import ToolContext, ToolResult


@tools.register(
    name="get_exam_summary",
    description="获取考试总览：各科平均分、最高分、最低分、得分率。",
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
            "exam_id": {"type": "string", "description": "考试 ID"},
        },
        "required": ["exam_id"],
    },
)
async def get_exam_summary(input: dict, ctx: ToolContext) -> ToolResult:
    exam_id = input.get("exam_id", "")
    try:
        from edu_cloud.modules.analytics.service import exam_summary
        data = await exam_summary(
            ctx.db, exam_id=exam_id, school_id=ctx.school_id,
            visible_subject_codes=ctx.subject_codes,
        )
        return ToolResult(success=True, data=data)
    except Exception as e:
        return ToolResult(success=False, error=str(e))


@tools.register(
    name="get_score_distribution",
    description="获取成绩分布（分数段统计）。可按科目和班级过滤。支持 exam_subject_id 单参数替代 exam_id+subject_id。",
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
        },
        "required": [],
    },
)
async def get_score_distribution(input: dict, ctx: ToolContext) -> ToolResult:
    exam_id = input.get("exam_id")
    subject_id = input.get("subject_id")
    exam_subject_id = input.get("exam_subject_id")
    class_id = input.get("class_id")
    try:
        if exam_subject_id and not exam_id:
            from edu_cloud.modules.analytics.service import resolve_subject_to_exam
            exam_id, _ = await resolve_subject_to_exam(ctx.db, exam_subject_id, ctx.school_id)
            subject_id = exam_subject_id
        if not exam_id:
            return ToolResult(success=False, error="需要提供 exam_id 或 exam_subject_id")
        if ctx.class_ids is not None and class_id and class_id not in ctx.class_ids:
            return ToolResult(success=False, error="无权访问该班级")
        from edu_cloud.modules.analytics.service import exam_distribution
        scope_classes = [class_id] if class_id else ctx.class_ids
        data = await exam_distribution(
            ctx.db, exam_id=exam_id, school_id=ctx.school_id,
            subject_id=subject_id,
            visible_subject_codes=ctx.subject_codes,
            visible_class_ids=scope_classes,
        )
        return ToolResult(success=True, data=data)
    except Exception as e:
        return ToolResult(success=False, error=str(e))


@tools.register(
    name="get_question_analysis",
    description="获取某科目每道题的得分率分析。",
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
            "subject_id": {"type": "string", "description": "科目 ID"},
        },
        "required": ["subject_id"],
    },
)
async def get_question_analysis(input: dict, ctx: ToolContext) -> ToolResult:
    subject_id = input.get("subject_id", "")
    try:
        from edu_cloud.modules.analytics.service import subject_question_analysis
        data = await subject_question_analysis(
            ctx.db, subject_id=subject_id, school_id=ctx.school_id,
            visible_subject_codes=ctx.subject_codes,
        )
        return ToolResult(success=True, data=data)
    except Exception as e:
        return ToolResult(success=False, error=str(e))


@tools.register(
    name="get_student_scores",
    description="获取某学生在某次考试的各科各题详细分数。",
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
            "exam_id": {"type": "string", "description": "考试 ID"},
            "student_id": {"type": "string", "description": "学生 ID"},
        },
        "required": ["exam_id", "student_id"],
    },
)
async def get_student_scores(input: dict, ctx: ToolContext) -> ToolResult:
    exam_id = input.get("exam_id", "")
    student_id = input.get("student_id", "")
    try:
        from edu_cloud.modules.student.service import get_student
        student = await get_student(ctx.db, student_id=student_id, school_id=ctx.school_id)
        if not student:
            return ToolResult(success=False, error="学生不存在")
        if ctx.class_ids is not None and student.class_id not in ctx.class_ids:
            return ToolResult(success=False, error="无权查看该学生成绩")

        from edu_cloud.modules.analytics.service import get_student_exam_scores
        all_scores = await get_student_exam_scores(
            ctx.db, exam_id=exam_id, student_id=student_id, school_id=ctx.school_id,
        )
        total = sum(s["score"] for s in all_scores)
        total_max = sum(s["max_score"] for s in all_scores)
        return ToolResult(success=True, data={
            "student_id": student_id,
            "student_name": student.name,
            "total_score": total,
            "total_max": total_max,
            "details": all_scores,
        })
    except Exception as e:
        return ToolResult(success=False, error=str(e))


@tools.register(
    name="get_class_scores",
    description="获取某班级在某次考试的学生成绩列表。支持 exam_subject_id 单参数替代 exam_id+subject_id。",
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
            "class_id": {"type": "string", "description": "班级 ID"},
            "subject_id": {"type": "string", "description": "可选，科目 ID"},
            "exam_subject_id": {"type": "string", "description": "科目 ID，自动解析 exam_id（与 exam_id 二选一）"},
        },
        "required": ["class_id"],
    },
)
async def get_class_scores(input: dict, ctx: ToolContext) -> ToolResult:
    exam_id = input.get("exam_id")
    class_id = input.get("class_id", "")
    subject_id = input.get("subject_id")
    exam_subject_id = input.get("exam_subject_id")
    try:
        if exam_subject_id and not exam_id:
            from edu_cloud.modules.analytics.service import resolve_subject_to_exam
            exam_id, _ = await resolve_subject_to_exam(ctx.db, exam_subject_id, ctx.school_id)
            subject_id = exam_subject_id
        if not exam_id:
            return ToolResult(success=False, error="需要提供 exam_id 或 exam_subject_id")
        if ctx.class_ids is not None and class_id not in ctx.class_ids:
            return ToolResult(success=False, error="无权访问该班级")

        from sqlalchemy import select
        from edu_cloud.modules.exam.models import Subject
        from edu_cloud.modules.student.models import Student
        from edu_cloud.modules.analytics.service import get_effective_scores

        students_result = await ctx.db.execute(
            select(Student).where(Student.class_id == class_id, Student.school_id == ctx.school_id)
        )
        students = {s.id: s for s in students_result.scalars().all()}

        subj_query = select(Subject).where(Subject.exam_id == exam_id, Subject.school_id == ctx.school_id)
        if subject_id:
            subj_query = subj_query.where(Subject.id == subject_id)
        if ctx.subject_codes is not None:
            subj_query = subj_query.where(Subject.code.in_(ctx.subject_codes))
        subjects = (await ctx.db.execute(subj_query)).scalars().all()

        student_totals: dict[str, float] = {}
        for subj in subjects:
            scores = await get_effective_scores(ctx.db, subj.id, ctx.school_id, [class_id])
            for s in scores:
                student_totals[s["student_id"]] = student_totals.get(s["student_id"], 0) + s["effective_score"]

        results = []
        for sid, total in sorted(student_totals.items(), key=lambda x: x[1], reverse=True):
            st = students.get(sid)
            results.append({
                "student_id": sid,
                "student_name": st.name if st else "",
                "total_score": total,
            })
        return ToolResult(success=True, data={"class_id": class_id, "students": results})
    except Exception as e:
        return ToolResult(success=False, error=str(e))
