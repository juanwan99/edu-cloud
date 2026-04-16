"""考试总览工具 — 读取预计算的 ExamAnalysisSnapshot。"""
import logging

from sqlalchemy import select

from edu_cloud.ai.registry import tools
from edu_cloud.ai.tool_context import ToolContext, ToolResult
from edu_cloud.models.agent_snapshot import ExamAnalysisSnapshot

logger = logging.getLogger(__name__)


@tools.register(
    name="get_exam_overview",
    description="获取考试总览：学校整体指标 + 各学科分项统计。数据来自预计算快照，响应快速。",
    parameters={
        "type": "object",
        "properties": {
            "exam_id": {"type": "string", "description": "考试 ID"},
        },
        "required": ["exam_id"],
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
async def get_exam_overview(input: dict, ctx: ToolContext) -> ToolResult:
    exam_id = input.get("exam_id", "")
    try:
        # Fetch school_overview snapshot
        stmt = (
            select(ExamAnalysisSnapshot)
            .where(
                ExamAnalysisSnapshot.exam_id == exam_id,
                ExamAnalysisSnapshot.school_id == ctx.school_id,
                ExamAnalysisSnapshot.snapshot_type == "school_overview",
                ExamAnalysisSnapshot.status == "ready",
            )
            .order_by(ExamAnalysisSnapshot.version.desc())
            .limit(1)
        )
        result = await ctx.db.execute(stmt)
        overview = result.scalar_one_or_none()

        if overview is None:
            return ToolResult(
                success=True,
                data={"status": "not_found", "message": "该考试暂无分析快照，可能尚未计算完成。"},
            )

        # Fetch subject breakdowns
        stmt_subjects = (
            select(ExamAnalysisSnapshot)
            .where(
                ExamAnalysisSnapshot.exam_id == exam_id,
                ExamAnalysisSnapshot.school_id == ctx.school_id,
                ExamAnalysisSnapshot.snapshot_type == "subject_detail",
                ExamAnalysisSnapshot.status == "ready",
            )
            .order_by(ExamAnalysisSnapshot.subject_code)
        )
        result_subjects = await ctx.db.execute(stmt_subjects)
        subjects = result_subjects.scalars().all()

        return ToolResult(
            success=True,
            data={
                "status": "ready",
                "school_overview": overview.metrics or {},
                "subject_breakdowns": [
                    {
                        "subject_code": s.subject_code,
                        "metrics": s.metrics or {},
                    }
                    for s in subjects
                ],
            },
        )
    except Exception as e:
        logger.exception("get_exam_overview failed")
        return ToolResult(success=False, error=str(e))
