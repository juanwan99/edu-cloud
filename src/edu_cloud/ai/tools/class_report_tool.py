"""班级考试报告工具 — 读取预计算的 ClassExamReport。"""
import logging

from sqlalchemy import select

from edu_cloud.ai.registry import tools
from edu_cloud.ai.tool_context import ToolContext, ToolResult
from edu_cloud.models.agent_snapshot import ClassExamReport

logger = logging.getLogger(__name__)


@tools.register(
    name="get_class_report",
    description="获取班级考试报告：班均分、年级排名、与年级均分对比。数据来自预计算快照。",
    parameters={
        "type": "object",
        "properties": {
            "exam_id": {"type": "string", "description": "考试 ID"},
            "class_id": {"type": "string", "description": "班级 ID"},
        },
        "required": ["exam_id", "class_id"],
    },
    category="analytics",
    domain="exam_query",
    allowed_roles=[
        "platform_admin", "district_admin", "principal",
        "academic_director", "grade_leader", "homeroom_teacher", "subject_teacher",
    ],
    risk_level="low",
    is_read_only=True,
)
async def get_class_report(input: dict, ctx: ToolContext) -> ToolResult:
    exam_id = input.get("exam_id", "")
    class_id = input.get("class_id", "")
    try:
        stmt = (
            select(ClassExamReport)
            .where(
                ClassExamReport.exam_id == exam_id,
                ClassExamReport.class_id == class_id,
                ClassExamReport.school_id == ctx.school_id,
            )
            .order_by(ClassExamReport.version.desc())
            .limit(1)
        )
        result = await ctx.db.execute(stmt)
        report = result.scalar_one_or_none()

        if report is None:
            return ToolResult(
                success=True,
                data={"status": "not_found", "message": "该班级暂无考试报告。"},
            )

        vs_grade_avg = None
        if report.class_avg is not None and report.grade_avg is not None:
            vs_grade_avg = round(report.class_avg - report.grade_avg, 2)

        return ToolResult(
            success=True,
            data={
                "class_id": report.class_id,
                "class_avg": report.class_avg,
                "grade_avg": report.grade_avg,
                "grade_rank": report.grade_rank,
                "vs_grade_avg": vs_grade_avg,
                "vs_last_exam": report.vs_last_exam,
                "metrics": report.metrics or {},
            },
        )
    except Exception as e:
        logger.exception("get_class_report failed")
        return ToolResult(success=False, error=str(e))
