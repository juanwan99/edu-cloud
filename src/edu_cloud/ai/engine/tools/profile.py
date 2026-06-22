"""Student profile tools — Pydantic AI native (migrated from ai/tools/profile.py)."""
from __future__ import annotations

import json

from pydantic_ai import RunContext

from edu_cloud.ai.engine.agent_deps import AgentDeps
from edu_cloud.ai.engine.tool_wrapper import edu_tool

_PROFILE_ROLES = frozenset({
    "platform_admin", "district_admin", "school_admin", "principal",
    "academic_director", "grade_leader",
    "homeroom_teacher", "subject_teacher",
})


@edu_tool(name="get_student_trend", module_code="study_analytics", domain="profile", allowed_roles=_PROFILE_ROLES, sensitivity="student")
async def get_student_trend(ctx: RunContext[AgentDeps], student_id: str, subject_code: str | None = None) -> str:
    """Get a student's exam score trend over time."""
    from edu_cloud.modules.profile.service import get_student_trend as svc

    scope = ctx.deps.data_scope
    async with ctx.deps.get_db() as db:
        data = await svc(db, student_id=student_id, school_id=scope.school_id, subject_code=subject_code)
    return json.dumps(data, ensure_ascii=False, default=str)


@edu_tool(name="get_student_knowledge_map", module_code="study_analytics", domain="profile", allowed_roles=_PROFILE_ROLES, sensitivity="student")
async def get_student_knowledge_map(ctx: RunContext[AgentDeps], student_id: str, course_code: str | None = None) -> str:
    """Get a student's knowledge mastery map."""
    from edu_cloud.modules.profile.service import get_student_knowledge_map as svc

    scope = ctx.deps.data_scope
    async with ctx.deps.get_db() as db:
        data = await svc(db, student_id=student_id, school_id=scope.school_id, course_code=course_code)
    return json.dumps(data, ensure_ascii=False, default=str)


@edu_tool(name="get_class_knowledge_weakness", module_code="study_analytics", domain="profile", allowed_roles=_PROFILE_ROLES, sensitivity="student")
async def get_class_knowledge_weakness(
    ctx: RunContext[AgentDeps], class_id: str, course_code: str | None = None, top_n: int = 10,
) -> str:
    """Get top N weak knowledge points for a class."""
    from sqlalchemy import select
    from edu_cloud.modules.student.models import Student
    from edu_cloud.modules.profile.service import get_class_knowledge_weakness as svc

    scope = ctx.deps.data_scope
    if scope.visible_class_ids is not None and class_id not in scope.visible_class_ids:
        return json.dumps({"error": "无权访问该班级"})
    async with ctx.deps.get_db() as db:
        student_ids = list((await db.execute(
            select(Student.id).where(Student.class_id == class_id, Student.school_id == scope.school_id)
        )).scalars().all())
        data = await svc(db, school_id=scope.school_id, class_student_ids=student_ids, course_code=course_code, top_n=top_n)
    return json.dumps(data, ensure_ascii=False, default=str)


@edu_tool(name="get_student_error_pattern", module_code="study_analytics", domain="profile", allowed_roles=_PROFILE_ROLES, sensitivity="student")
async def get_student_error_pattern(ctx: RunContext[AgentDeps], student_id: str, subject_code: str | None = None) -> str:
    """Get a student's error pattern analysis."""
    from edu_cloud.modules.profile.service import get_student_error_pattern as svc

    scope = ctx.deps.data_scope
    async with ctx.deps.get_db() as db:
        data = await svc(db, student_id=student_id, school_id=scope.school_id, subject_code=subject_code)
    return json.dumps(data, ensure_ascii=False, default=str)


ALL_TOOLS = [get_student_trend, get_student_knowledge_map, get_class_knowledge_weakness, get_student_error_pattern]
