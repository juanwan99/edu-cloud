"""Cross-school analytics tools — Pydantic AI native (migrated from ai/tools/analytics.py)."""
from __future__ import annotations

import json
import statistics

from pydantic_ai import RunContext
from sqlalchemy import select

from edu_cloud.ai.engine.agent_deps import AgentDeps
from edu_cloud.ai.engine.tool_wrapper import edu_tool

_CROSS_SCHOOL_ROLES = frozenset({"platform_admin", "district_admin"})


def _compute_stats(scores: list[float]) -> dict:
    if not scores:
        return {"count": 0, "avg": None, "max": None, "min": None, "median": None}
    return {
        "count": len(scores),
        "avg": round(sum(scores) / len(scores), 2),
        "max": round(max(scores), 2),
        "min": round(min(scores), 2),
        "median": round(statistics.median(scores), 2),
    }


@edu_tool(name="get_exam_scores", module_code="exam", domain="analytics", allowed_roles=_CROSS_SCHOOL_ROLES, sensitivity="student")
async def get_exam_scores(ctx: RunContext[AgentDeps], exam_id: str) -> str:
    """Get student score list for an exam (with class info), ranked by total score."""
    from edu_cloud.models.exam import ExamResult
    from edu_cloud.models.student import Student

    scope = ctx.deps.data_scope
    async with ctx.deps.get_db() as db:
        stmt = (
            select(ExamResult, Student)
            .join(Student, ExamResult.student_id == Student.id)
            .where(ExamResult.exam_id == exam_id)
        )
        if scope.school_id:
            stmt = stmt.where(ExamResult.school_id == scope.school_id)
        if scope.visible_class_ids:
            stmt = stmt.where(Student.class_id.in_(scope.visible_class_ids))
        rows = (await db.execute(stmt)).all()

    students_data = []
    scores = []
    for result, student in rows:
        students_data.append({
            "student_id": student.id, "name": student.name,
            "student_number": student.student_number, "class_id": student.class_id,
            "grade": student.grade, "total_score": result.total_score,
        })
        scores.append(result.total_score)
    students_data.sort(key=lambda x: x["total_score"], reverse=True)
    for rank, s in enumerate(students_data, start=1):
        s["rank"] = rank
    return json.dumps({"exam_id": exam_id, "students": students_data, "stats": _compute_stats(scores)}, ensure_ascii=False, default=str)


@edu_tool(name="get_class_stats", module_code="exam", domain="analytics", allowed_roles=_CROSS_SCHOOL_ROLES, sensitivity="school")
async def get_class_stats(ctx: RunContext[AgentDeps], exam_id: str, class_id: str) -> str:
    """Get class statistics for an exam (avg/max/min/median/count)."""
    from edu_cloud.models.exam import ExamResult
    from edu_cloud.models.student import Student
    from edu_cloud.models.class_group import ClassGroup

    scope = ctx.deps.data_scope
    if scope.visible_class_ids is not None and class_id not in scope.visible_class_ids:
        return json.dumps({"error": "无权访问此班级数据"})

    async with ctx.deps.get_db() as db:
        stmt = (
            select(ExamResult.total_score)
            .join(Student, ExamResult.student_id == Student.id)
            .where(ExamResult.exam_id == exam_id, Student.class_id == class_id)
        )
        if scope.school_id:
            stmt = stmt.where(ExamResult.school_id == scope.school_id)
        scores = list((await db.execute(stmt)).scalars().all())

        cls_row = (await db.execute(select(ClassGroup).where(ClassGroup.id == class_id))).scalar_one_or_none()
        class_name = cls_row.name if cls_row else None

    return json.dumps({"exam_id": exam_id, "class_id": class_id, "class_name": class_name, **_compute_stats(scores)}, ensure_ascii=False, default=str)


ALL_TOOLS = [get_exam_scores, get_class_stats]
