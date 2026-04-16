"""Agent 工具 — 作业查询/布置/统计。"""
from edu_cloud.ai.registry import tools
from edu_cloud.ai.tool_context import ToolContext, ToolResult
from edu_cloud.modules.homework.service import HomeworkTaskService, HomeworkSubmissionService


@tools.register(
    name="list_homework_tasks",
    description="列出作业，支持按班级、科目、状态过滤",
    parameters={
        "type": "object",
        "properties": {
            "class_id": {"type": "string", "description": "班级 ID（可选）"},
            "subject_code": {"type": "string", "description": "科目代码（可选）"},
            "status": {"type": "string", "description": "状态过滤: draft/active/expired/closed（可选）"},
        },
        "required": [],
    },
    category="L2_homework",
    module_code="homework",
    domain="homework",
    risk_level="low",
    is_read_only=True,
    sensitivity="school",
    requires_capabilities=[("homework", "read")],
    allowed_roles=["platform_admin", "district_admin", "principal", "academic_director",
                   "grade_leader", "homeroom_teacher", "subject_teacher", "parent"],
)
async def list_homework_tasks(input: dict, ctx: ToolContext) -> ToolResult:
    class_id = input.get("class_id")
    subject_code = input.get("subject_code")
    status = input.get("status")
    try:
        tasks = await HomeworkTaskService.list_tasks(
            ctx.db, school_id=ctx.school_id,
            class_id=class_id or None, subject_code=subject_code or None,
            status=status or None,
        )
        return ToolResult(success=True, data={"tasks": [
            {"id": t.id, "title": t.title, "type": t.task_type,
             "status": t.status, "subject": t.subject_code}
            for t in tasks[:20]
        ]})
    except Exception as e:
        return ToolResult(success=False, error=str(e))


@tools.register(
    name="get_homework_stats",
    description="查看指定作业的提交统计：总数/已提交/已批改/提交率/平均分",
    parameters={
        "type": "object",
        "properties": {
            "task_id": {"type": "string", "description": "作业 ID"},
        },
        "required": ["task_id"],
    },
    category="L2_homework",
    module_code="homework",
    domain="homework",
    risk_level="low",
    is_read_only=True,
    sensitivity="school",
    requires_capabilities=[("homework", "read")],
    allowed_roles=["platform_admin", "district_admin", "principal", "academic_director",
                   "grade_leader", "homeroom_teacher", "subject_teacher"],
)
async def get_homework_stats(input: dict, ctx: ToolContext) -> ToolResult:
    task_id = input.get("task_id", "")
    try:
        await HomeworkTaskService.get_task(ctx.db, task_id=task_id, school_id=ctx.school_id)
        data = await HomeworkSubmissionService.get_task_stats(ctx.db, task_id=task_id)
        return ToolResult(success=True, data=data)
    except Exception as e:
        return ToolResult(success=False, error=str(e))


@tools.register(
    name="get_submission_details",
    description="查看某作业的提交明细列表，支持按状态过滤",
    parameters={
        "type": "object",
        "properties": {
            "task_id": {"type": "string", "description": "作业 ID"},
            "status": {"type": "string", "description": "状态过滤: pending/submitted/graded（可选）"},
        },
        "required": ["task_id"],
    },
    category="L2_homework",
    module_code="homework",
    domain="homework",
    risk_level="low",
    is_read_only=True,
    sensitivity="school",
    requires_capabilities=[("homework", "read")],
    allowed_roles=["platform_admin", "district_admin", "principal", "academic_director",
                   "grade_leader", "homeroom_teacher", "subject_teacher"],
)
async def get_submission_details(input: dict, ctx: ToolContext) -> ToolResult:
    task_id = input.get("task_id", "")
    status = input.get("status")
    try:
        await HomeworkTaskService.get_task(ctx.db, task_id=task_id, school_id=ctx.school_id)
        subs = await HomeworkSubmissionService.list_submissions(
            ctx.db, task_id=task_id, status=status or None,
        )
        return ToolResult(success=True, data={"submissions": [
            {"id": s.id, "student_id": s.student_id, "status": s.status,
             "score": s.score, "submit_time": str(s.submit_time) if s.submit_time else None}
            for s in subs
        ]})
    except Exception as e:
        return ToolResult(success=False, error=str(e))


@tools.register(
    name="assign_homework",
    description="创建并发布一份作业（写操作）",
    parameters={
        "type": "object",
        "properties": {
            "title": {"type": "string", "description": "作业标题"},
            "subject_code": {"type": "string", "description": "科目代码"},
            "class_id": {"type": "string", "description": "班级 ID"},
            "deadline": {"type": "string", "description": "截止时间（可选）"},
        },
        "required": ["title", "subject_code", "class_id"],
    },
    category="L2_homework",
    module_code="homework",
    domain="homework",
    risk_level="med",
    is_read_only=False,
    sensitivity="school",
    requires_capabilities=[("homework", "write")],
    allowed_roles=["homeroom_teacher", "subject_teacher", "academic_director", "platform_admin"],
)
async def assign_homework(input: dict, ctx: ToolContext) -> ToolResult:
    title = input.get("title", "")
    subject_code = input.get("subject_code", "")
    class_id = input.get("class_id", "")
    try:
        task = await HomeworkTaskService.create_task(
            ctx.db, school_id=ctx.school_id, title=title,
            task_type="regular", subject_code=subject_code,
            class_id=class_id, assigned_by=ctx.user_id,
        )
        task = await HomeworkTaskService.transition_status(
            ctx.db, task_id=task.id, school_id=ctx.school_id, action="publish",
        )
        return ToolResult(success=True, data={"task_id": task.id, "title": task.title, "status": task.status})
    except Exception as e:
        return ToolResult(success=False, error=str(e))


@tools.register(
    name="recommend_remedial",
    description="根据考试成绩推荐考后补偿作业内容（开发中）",
    parameters={
        "type": "object",
        "properties": {
            "exam_id": {"type": "string", "description": "考试 ID"},
        },
        "required": ["exam_id"],
    },
    category="L2_homework",
    module_code="homework",
    domain="homework",
    risk_level="low",
    is_read_only=True,
    sensitivity="school",
    requires_capabilities=[("homework", "read")],
    allowed_roles=["homeroom_teacher", "subject_teacher", "academic_director", "platform_admin"],
)
async def recommend_remedial(input: dict, ctx: ToolContext) -> ToolResult:
    return ToolResult(success=True, data={"message": "考后补偿推荐功能开发中，将在 Phase 3 学情分析完成后实现"})
