"""考试域工具（3 个）。L1_exam 类别。"""
from edu_cloud.ai.registry import tools
from edu_cloud.ai.tool_context import ToolContext, ToolResult


@tools.register(
    name="get_exam_list",
    description="获取考试列表。可按状态过滤（draft/scanning/grading/reviewing/completed）。",
    category="L1_exam",
    module_code="exam",
    domain="exam",
    allowed_roles=["platform_admin", "district_admin", "principal", "academic_director", "grade_leader", "homeroom_teacher", "subject_teacher"],
    risk_level="low",
    is_read_only=True,
    sensitivity="school",
    parameters={
        "type": "object",
        "properties": {
            "status": {"type": "string", "description": "可选，考试状态过滤"},
        },
        "required": [],
    },
)
async def get_exam_list(input: dict, ctx: ToolContext) -> ToolResult:
    status = input.get("status")
    try:
        from edu_cloud.modules.exam.service import list_exams
        exams = await list_exams(ctx.db, school_id=ctx.school_id)
        if status:
            exams = [e for e in exams if e.status == status]
        return ToolResult(success=True, data={
            "exams": [
                {"id": e.id, "name": e.name, "status": e.status, "card_title": e.card_title}
                for e in exams
            ]
        })
    except Exception as e:
        return ToolResult(success=False, error=str(e))


@tools.register(
    name="get_exam_detail",
    description="获取考试详情，包括科目列表。",
    category="L1_exam",
    module_code="exam",
    domain="exam",
    allowed_roles=["platform_admin", "district_admin", "principal", "academic_director", "grade_leader", "homeroom_teacher", "subject_teacher"],
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
async def get_exam_detail(input: dict, ctx: ToolContext) -> ToolResult:
    exam_id = input.get("exam_id", "")
    try:
        from edu_cloud.modules.exam.service import get_exam, list_subjects
        exam = await get_exam(ctx.db, exam_id=exam_id, school_id=ctx.school_id)
        subjects = await list_subjects(ctx.db, exam_id=exam_id, school_id=ctx.school_id)
        if ctx.subject_codes is not None:
            subjects = [s for s in subjects if s.code in ctx.subject_codes]
        return ToolResult(success=True, data={
            "id": exam.id,
            "name": exam.name,
            "status": exam.status,
            "subjects": [
                {"id": s.id, "name": s.name, "code": s.code}
                for s in subjects
            ],
        })
    except Exception as e:
        return ToolResult(success=False, error=str(e))


@tools.register(
    name="get_subject_questions",
    description="获取某科目的题目列表。",
    category="L1_exam",
    module_code="exam",
    domain="exam",
    allowed_roles=["platform_admin", "district_admin", "principal", "academic_director", "grade_leader", "homeroom_teacher", "subject_teacher"],
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
async def get_subject_questions(input: dict, ctx: ToolContext) -> ToolResult:
    subject_id = input.get("subject_id", "")
    try:
        if ctx.subject_codes is not None:
            from sqlalchemy import select
            from edu_cloud.modules.exam.models import Subject
            subj_result = await ctx.db.execute(
                select(Subject).where(Subject.id == subject_id, Subject.school_id == ctx.school_id)
            )
            subj = subj_result.scalar_one_or_none()
            if subj and subj.code not in ctx.subject_codes:
                return ToolResult(success=False, error="无权访问该科目")
        from edu_cloud.modules.exam.service import list_questions
        questions = await list_questions(ctx.db, subject_id=subject_id, school_id=ctx.school_id)
        return ToolResult(success=True, data={
            "questions": [
                {"id": q.id, "name": q.name, "question_type": q.question_type, "max_score": q.max_score}
                for q in questions
            ]
        })
    except Exception as e:
        return ToolResult(success=False, error=str(e))
