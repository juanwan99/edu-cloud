"""Exam tools — Pydantic AI native (migrated from ai/tools/exams.py)."""
from __future__ import annotations

import json

from pydantic_ai import RunContext

from edu_cloud.ai.engine.agent_deps import AgentDeps
from edu_cloud.ai.engine.tool_wrapper import edu_tool

_EXAM_ROLES = frozenset({
    "platform_admin", "district_admin", "school_admin", "principal",
    "academic_director", "grade_leader",
    "homeroom_teacher", "subject_teacher",
})


@edu_tool(name="get_exam_list", module_code="exam", domain="exam", allowed_roles=_EXAM_ROLES, sensitivity="school")
async def get_exam_list(ctx: RunContext[AgentDeps], status: str | None = None) -> str:
    """Get exam list. Optionally filter by status (draft/scanning/grading/reviewing/completed)."""
    from edu_cloud.modules.exam.service import list_exams

    scope = ctx.deps.data_scope
    async with ctx.deps.get_db() as db:
        exams = await list_exams(db, school_id=scope.school_id)
    if status:
        exams = [e for e in exams if e.status == status]
    return json.dumps({
        "exams": [{"id": e.id, "name": e.name, "status": e.status, "card_title": e.card_title} for e in exams]
    }, ensure_ascii=False)


@edu_tool(name="get_exam_detail", module_code="exam", domain="exam", allowed_roles=_EXAM_ROLES, sensitivity="school")
async def get_exam_detail(ctx: RunContext[AgentDeps], exam_id: str) -> str:
    """Get exam details including subject list."""
    from edu_cloud.modules.exam.service import get_exam, list_subjects

    scope = ctx.deps.data_scope
    async with ctx.deps.get_db() as db:
        exam = await get_exam(db, exam_id=exam_id, school_id=scope.school_id)
        subjects = await list_subjects(db, exam_id=exam_id, school_id=scope.school_id)
    if scope.visible_subject_codes is not None:
        subjects = [s for s in subjects if s.code in scope.visible_subject_codes]
    return json.dumps({
        "id": exam.id, "name": exam.name, "status": exam.status,
        "subjects": [{"id": s.id, "name": s.name, "code": s.code} for s in subjects],
    }, ensure_ascii=False)


@edu_tool(name="get_subject_questions", module_code="exam", domain="exam", allowed_roles=_EXAM_ROLES, sensitivity="school")
async def get_subject_questions(ctx: RunContext[AgentDeps], subject_id: str) -> str:
    """Get questions for a subject."""
    from edu_cloud.modules.exam.service import list_questions

    scope = ctx.deps.data_scope
    async with ctx.deps.get_db() as db:
        if scope.visible_subject_codes is not None:
            from sqlalchemy import select
            from edu_cloud.modules.exam.models import Subject
            subj = (await db.execute(
                select(Subject).where(Subject.id == subject_id, Subject.school_id == scope.school_id)
            )).scalar_one_or_none()
            if subj and subj.code not in scope.visible_subject_codes:
                return json.dumps({"error": "无权访问该科目"})
        questions = await list_questions(db, subject_id=subject_id, school_id=scope.school_id)
    return json.dumps({
        "questions": [{"id": q.id, "name": q.name, "question_type": q.question_type, "max_score": q.max_score} for q in questions]
    }, ensure_ascii=False)


ALL_TOOLS = [get_exam_list, get_exam_detail, get_subject_questions]
