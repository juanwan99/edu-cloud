"""L2 跨校分析工具 — 联考/跨校成绩查询。

校本分析工具已迁移到 analytics_score.py / analytics_compare.py（Batch 4）。
compare_classes / get_student_profile 已被新工具替代，从本文件移除。
"""
import statistics
import logging
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from edu_cloud.ai.registry import tools
from edu_cloud.ai.tool_context import ToolContext, ToolResult
from edu_cloud.models.exam import Exam, ExamResult
from edu_cloud.models.student import Student
from edu_cloud.models.class_group import ClassGroup

logger = logging.getLogger(__name__)


def _compute_stats(scores: list[float]) -> dict:
    """计算 count/avg/max/min/median 统计。"""
    if not scores:
        return {"count": 0, "avg": None, "max": None, "min": None, "median": None}
    return {
        "count": len(scores),
        "avg": round(sum(scores) / len(scores), 2),
        "max": round(max(scores), 2),
        "min": round(min(scores), 2),
        "median": round(statistics.median(scores), 2),
    }


@tools.register(
    name="get_exam_scores",
    description="获取指定考试的学生成绩列表（含班级信息），按总分降序排列，附整体统计数据。",
    parameters={
        "type": "object",
        "properties": {
            "exam_id": {"type": "string", "description": "考试 ID"},
        },
        "required": ["exam_id"],
    },
    category="L2_cross_school",
    module_code="exam",
    domain="analytics",
    allowed_roles=["platform_admin", "district_admin"],
    risk_level="low",
    is_read_only=True,
    sensitivity="school",
)
async def get_exam_scores(input: dict, ctx: ToolContext) -> ToolResult:
    exam_id = input.get("exam_id", "")
    try:
        stmt = (
            select(ExamResult, Student)
            .join(Student, ExamResult.student_id == Student.id)
            .where(ExamResult.exam_id == exam_id)
        )
        if ctx.school_id:
            stmt = stmt.where(ExamResult.school_id == ctx.school_id)
        if ctx.class_ids:
            stmt = stmt.where(Student.class_id.in_(ctx.class_ids))

        rows = (await ctx.db.execute(stmt)).all()

        students_data = []
        scores = []
        for result, student in rows:
            students_data.append({
                "student_id": student.id,
                "name": student.name,
                "student_number": student.student_number,
                "class_id": student.class_id,
                "grade": student.grade,
                "total_score": result.total_score,
            })
            scores.append(result.total_score)

        students_data.sort(key=lambda x: x["total_score"], reverse=True)
        for rank, s in enumerate(students_data, start=1):
            s["rank"] = rank

        return ToolResult(success=True, data={
            "exam_id": exam_id,
            "students": students_data,
            "stats": _compute_stats(scores),
        })
    except Exception as e:
        return ToolResult(success=False, error=str(e))


@tools.register(
    name="get_class_stats",
    description="获取指定班级在某场考试中的成绩统计（均值/最高/最低/中位数/人数）。",
    parameters={
        "type": "object",
        "properties": {
            "exam_id": {"type": "string", "description": "考试 ID"},
            "class_id": {"type": "string", "description": "班级 ID"},
        },
        "required": ["exam_id", "class_id"],
    },
    category="L2_cross_school",
    module_code="exam",
    domain="analytics",
    allowed_roles=["platform_admin", "district_admin"],
    risk_level="low",
    is_read_only=True,
    sensitivity="school",
)
async def get_class_stats(input: dict, ctx: ToolContext) -> ToolResult:
    exam_id = input.get("exam_id", "")
    class_id = input.get("class_id", "")
    try:
        # Scope enforcement: restrict to caller's classes
        if ctx.class_ids is not None and class_id not in ctx.class_ids:
            return ToolResult(success=False, error="无权访问此班级数据")

        stmt = (
            select(ExamResult.total_score)
            .join(Student, ExamResult.student_id == Student.id)
            .where(ExamResult.exam_id == exam_id)
            .where(Student.class_id == class_id)
        )
        if ctx.school_id:
            stmt = stmt.where(ExamResult.school_id == ctx.school_id)

        rows = (await ctx.db.execute(stmt)).scalars().all()
        scores = list(rows)

        class_name = None
        cls_row = (await ctx.db.execute(select(ClassGroup).where(ClassGroup.id == class_id))).scalar_one_or_none()
        if cls_row:
            class_name = cls_row.name

        stats = _compute_stats(scores)
        return ToolResult(success=True, data={
            "exam_id": exam_id,
            "class_id": class_id,
            "class_name": class_name,
            **stats,
        })
    except Exception as e:
        return ToolResult(success=False, error=str(e))


# compare_classes → superseded by analytics_compare.py (L2_analytics)
# get_student_profile → superseded by students.py (L1_student)
