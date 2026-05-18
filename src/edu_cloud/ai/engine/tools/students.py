"""Student/class tools — Pydantic AI native (migrated from ai/tools/students.py)."""
from __future__ import annotations

import json

from pydantic_ai import RunContext

from edu_cloud.ai.engine.agent_deps import AgentDeps
from edu_cloud.ai.engine.tool_wrapper import edu_tool

_STUDENT_ROLES = frozenset({
    "platform_admin", "district_admin", "school_admin", "principal",
    "academic_director", "grade_leader",
    "homeroom_teacher", "subject_teacher",
})


@edu_tool(
    name="get_class_list",
    module_code="exam",
    domain="student",
    allowed_roles=_STUDENT_ROLES,
    sensitivity="school",
)
async def get_class_list(ctx: RunContext[AgentDeps], grade: str | None = None) -> str:
    """Get the list of classes. Optionally filter by grade (e.g. '高二')."""
    from edu_cloud.modules.student.service import list_classes

    scope = ctx.deps.data_scope
    async with ctx.deps.get_db() as db:
        classes = await list_classes(
            db, school_id=scope.school_id,
            visible_class_ids=scope.visible_class_ids,
        )
    if grade:
        classes = [c for c in classes if c.grade == grade]
    return json.dumps({
        "classes": [{"id": c.id, "name": c.name, "grade": c.grade} for c in classes]
    }, ensure_ascii=False)


@edu_tool(
    name="get_class_roster",
    module_code="exam",
    domain="student",
    allowed_roles=_STUDENT_ROLES,
    sensitivity="student",
)
async def get_class_roster(ctx: RunContext[AgentDeps], class_id: str) -> str:
    """Get the student roster for a class. Names are anonymized."""
    from edu_cloud.modules.student.service import list_students

    scope = ctx.deps.data_scope
    if scope.visible_class_ids is not None and class_id not in scope.visible_class_ids:
        return json.dumps({"error": "无权访问该班级", "students": []})

    async with ctx.deps.get_db() as db:
        students = await list_students(
            db, school_id=scope.school_id,
            class_id=class_id,
            visible_class_ids=scope.visible_class_ids,
        )
    return json.dumps({
        "students": [
            {"id": s.id, "student_name": s.name,
             "student_number": s.student_number, "class_id": s.class_id}
            for s in students
        ]
    }, ensure_ascii=False)


@edu_tool(
    name="search_students",
    module_code="exam",
    domain="student",
    allowed_roles=_STUDENT_ROLES,
    sensitivity="student",
)
async def search_students(ctx: RunContext[AgentDeps], query_string: str) -> str:
    """Search students by name (fuzzy match)."""
    from edu_cloud.modules.student.service import search_students as svc_search

    scope = ctx.deps.data_scope
    async with ctx.deps.get_db() as db:
        students = await svc_search(
            db, school_id=scope.school_id,
            query=query_string,
            visible_class_ids=scope.visible_class_ids,
        )
    return json.dumps({
        "students": [
            {"id": s.id, "student_name": s.name,
             "student_number": s.student_number, "class_id": s.class_id}
            for s in students
        ]
    }, ensure_ascii=False)


@edu_tool(
    name="get_student_profile",
    module_code="exam",
    domain="student",
    allowed_roles=_STUDENT_ROLES,
    sensitivity="student",
)
async def get_student_profile(ctx: RunContext[AgentDeps], student_id: str) -> str:
    """Get a student's profile information."""
    from edu_cloud.modules.student.service import get_student

    scope = ctx.deps.data_scope
    async with ctx.deps.get_db() as db:
        student = await get_student(db, student_id=student_id, school_id=scope.school_id)
    if not student:
        return json.dumps({"error": "学生不存在"})
    if scope.visible_class_ids is not None and student.class_id not in scope.visible_class_ids:
        return json.dumps({"error": "无权访问该学生信息"})
    return json.dumps({
        "id": student.id, "student_name": student.name,
        "student_number": student.student_number, "class_id": student.class_id,
    }, ensure_ascii=False)


ALL_TOOLS = [get_class_list, get_class_roster, search_students, get_student_profile]
