"""学生诊断工具 — 读取预计算的 StudentExamSnapshot。"""
import logging

from sqlalchemy import select

from edu_cloud.ai.registry import tools
from edu_cloud.ai.tool_context import ToolContext, ToolResult
from edu_cloud.modules.profile.models import StudentExamSnapshot

logger = logging.getLogger(__name__)


@tools.register(
    name="get_student_diagnosis",
    description="获取学生单次考试诊断：得分率、班级/年级排名、知识点得分、错误摘要。不传 exam_id 返回最近一次。",
    parameters={
        "type": "object",
        "properties": {
            "student_id": {"type": "string", "description": "学生 ID"},
            "exam_id": {"type": "string", "description": "考试 ID（可选，不传则取最近一次）"},
        },
        "required": ["student_id"],
    },
    category="analytics",
    domain="exam_query",
    allowed_roles=[
        "platform_admin", "district_admin", "principal",
        "academic_director", "grade_leader", "homeroom_teacher", "subject_teacher", "parent",
    ],
    risk_level="low",
    is_read_only=True,
)
async def get_student_diagnosis(input: dict, ctx: ToolContext) -> ToolResult:
    student_id = input.get("student_id", "")
    exam_id = input.get("exam_id")
    try:
        stmt = select(StudentExamSnapshot).where(
            StudentExamSnapshot.student_id == student_id,
            StudentExamSnapshot.school_id == ctx.school_id,
        )
        if exam_id:
            stmt = stmt.where(StudentExamSnapshot.exam_id == exam_id)

        # Get latest by created_at desc
        stmt = stmt.order_by(StudentExamSnapshot.created_at.desc()).limit(1)

        result = await ctx.db.execute(stmt)
        snapshot = result.scalar_one_or_none()

        if snapshot is None:
            return ToolResult(
                success=True,
                data={"status": "not_found", "message": "暂无该学生的考试诊断数据。"},
            )

        return ToolResult(
            success=True,
            data={
                "student_id": snapshot.student_id,
                "exam_id": snapshot.exam_id,
                "subject_code": snapshot.subject_code,
                "total_score": snapshot.total_score,
                "max_score": snapshot.max_score,
                "score_rate": snapshot.score_rate,
                "class_rank": snapshot.class_rank,
                "grade_rank": snapshot.grade_rank,
                "class_size": snapshot.class_size,
                "grade_size": snapshot.grade_size,
                "knowledge_scores": snapshot.knowledge_scores or {},
                "error_summary": snapshot.error_summary or {},
            },
        )
    except Exception as e:
        logger.exception("get_student_diagnosis failed")
        return ToolResult(success=False, error=str(e))
