"""Agent 工具 — 阅卷进度/质量/分配。"""
from edu_cloud.ai.registry import tools
from edu_cloud.ai.tool_context import ToolContext, ToolResult
from edu_cloud.modules.grading.assignment_service import GradingAssignmentService
from edu_cloud.modules.grading.quality_service import QualityCheckService


@tools.register(
    name="get_grading_progress",
    description="获取考试阅卷进度汇总：总任务数、完成/进行中/待开始数、按教师明细",
    parameters={
        "type": "object",
        "properties": {"exam_id": {"type": "string", "description": "考试 ID"}},
        "required": ["exam_id"],
    },
    category="L1_exam",
    module_code="grading",
    domain="exam",
    risk_level="low",
    is_read_only=True,
    sensitivity="school",
    allowed_roles=["platform_admin", "district_admin", "principal", "academic_director", "grade_leader", "homeroom_teacher", "subject_teacher"],
)
async def get_grading_progress(input: dict, ctx: ToolContext) -> ToolResult:
    exam_id = input.get("exam_id", "")
    try:
        data = await GradingAssignmentService.get_progress(ctx.db, exam_id, school_id=ctx.school_id)
        return ToolResult(success=True, data=data)
    except Exception as e:
        return ToolResult(success=False, error=str(e))


@tools.register(
    name="get_quality_report",
    description="获取阅卷质量报告：抽检数量、平均偏差、高严重度问题数",
    parameters={
        "type": "object",
        "properties": {"exam_id": {"type": "string", "description": "考试 ID"}},
        "required": ["exam_id"],
    },
    category="L2_analytics",
    module_code="grading",
    domain="exam",
    risk_level="low",
    is_read_only=True,
    sensitivity="school",
    allowed_roles=["platform_admin", "academic_director"],
)
async def get_quality_report(input: dict, ctx: ToolContext) -> ToolResult:
    exam_id = input.get("exam_id", "")
    try:
        data = await QualityCheckService.get_quality_report(ctx.db, exam_id, school_id=ctx.school_id)
        return ToolResult(success=True, data=data)
    except Exception as e:
        return ToolResult(success=False, error=str(e))


@tools.register(
    name="assign_grading_task",
    description="自动分配阅卷任务：按题目均匀分配给指定教师列表",
    parameters={
        "type": "object",
        "properties": {
            "exam_id": {"type": "string", "description": "考试 ID"},
            "subject_id": {"type": "string", "description": "科目 ID"},
            "question_ids": {"type": "string", "description": "题目 ID 列表，逗号分隔"},
            "teacher_ids": {"type": "string", "description": "教师 ID 列表，逗号分隔"},
            "total_count_per_question": {"type": "string", "description": "每题答卷数量（整数字符串），默认 0"},
        },
        "required": ["exam_id", "subject_id", "question_ids", "teacher_ids"],
    },
    category="L4_action",
    module_code="grading",
    domain="exam",
    risk_level="med",
    is_read_only=False,
    sensitivity="school",
    allowed_roles=["platform_admin", "academic_director"],
)
async def assign_grading_task(input: dict, ctx: ToolContext) -> ToolResult:
    exam_id = input.get("exam_id", "")
    subject_id = input.get("subject_id", "")
    question_ids = input.get("question_ids", "")
    teacher_ids = input.get("teacher_ids", "")
    total_count_per_question = input.get("total_count_per_question", "0")
    try:
        q_list = [q.strip() for q in question_ids.split(",") if q.strip()]
        t_list = [t.strip() for t in teacher_ids.split(",") if t.strip()]
        assignments = await GradingAssignmentService.auto_assign(
            ctx.db, exam_id=exam_id, subject_id=subject_id,
            question_ids=q_list, teacher_ids=t_list, school_id=ctx.school_id,
            total_count_per_question=int(total_count_per_question) if total_count_per_question else 0,
        )
        return ToolResult(success=True, data={
            "assigned": len(assignments),
            "teachers": [a.assigned_to for a in assignments],
        })
    except Exception as e:
        return ToolResult(success=False, error=str(e))
