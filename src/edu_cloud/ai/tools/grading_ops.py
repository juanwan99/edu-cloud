"""Agent 工具 — 阅卷进度/质量/分配。"""
from edu_cloud.ai.registry import tools
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
)
async def get_grading_progress(exam_id: str, _db=None, _school_id: str = ""):
    return await GradingAssignmentService.get_progress(_db, exam_id, school_id=_school_id)


@tools.register(
    name="get_quality_report",
    description="获取阅卷质量报告：抽检数量、平均偏差、高严重度问题数",
    parameters={
        "type": "object",
        "properties": {"exam_id": {"type": "string", "description": "考试 ID"}},
        "required": ["exam_id"],
    },
    category="L2_analytics",
)
async def get_quality_report(exam_id: str, _db=None, _school_id: str = ""):
    return await QualityCheckService.get_quality_report(_db, exam_id, school_id=_school_id)


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
        },
        "required": ["exam_id", "subject_id", "question_ids", "teacher_ids"],
    },
    category="L4_action",
)
async def assign_grading_task(
    exam_id: str, subject_id: str,
    question_ids: str, teacher_ids: str,
    _db=None, _school_id: str = "",
):
    q_list = [q.strip() for q in question_ids.split(",") if q.strip()]
    t_list = [t.strip() for t in teacher_ids.split(",") if t.strip()]
    assignments = await GradingAssignmentService.auto_assign(
        _db, exam_id=exam_id, subject_id=subject_id,
        question_ids=q_list, teacher_ids=t_list, school_id=_school_id,
    )
    return {
        "assigned": len(assignments),
        "teachers": [a.assigned_to for a in assignments],
    }
