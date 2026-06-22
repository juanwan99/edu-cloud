"""Score analytics tools — Pydantic AI native (migrated from ai/tools/analytics_score.py)."""
from __future__ import annotations

import json

from pydantic_ai import RunContext

from edu_cloud.ai.engine.agent_deps import AgentDeps
from edu_cloud.ai.engine.tool_wrapper import edu_tool

_ANALYTICS_ROLES = frozenset({"platform_admin", "academic_director", "grade_leader"})


@edu_tool(name="get_exam_summary", module_code="study_analytics", domain="analytics", allowed_roles=_ANALYTICS_ROLES, sensitivity="school")
async def get_exam_summary(ctx: RunContext[AgentDeps], exam_id: str) -> str:
    """Get exam overview: per-subject avg/max/min/score-rate."""
    from edu_cloud.modules.analytics.service import exam_summary

    scope = ctx.deps.data_scope
    async with ctx.deps.get_db() as db:
        data = await exam_summary(
            db, exam_id=exam_id, school_id=scope.school_id,
            visible_subject_codes=scope.visible_subject_codes,
        )
    return json.dumps(data, ensure_ascii=False, default=str)


@edu_tool(name="get_score_distribution", module_code="study_analytics", domain="analytics", allowed_roles=_ANALYTICS_ROLES, sensitivity="school")
async def get_score_distribution(
    ctx: RunContext[AgentDeps],
    exam_id: str | None = None,
    subject_id: str | None = None,
    exam_subject_id: str | None = None,
    class_id: str | None = None,
) -> str:
    """Get score distribution (segment stats). Supports exam_subject_id as shorthand."""
    scope = ctx.deps.data_scope
    async with ctx.deps.get_db() as db:
        if exam_subject_id and not exam_id:
            from edu_cloud.modules.analytics.service import resolve_subject_to_exam
            exam_id, _ = await resolve_subject_to_exam(db, exam_subject_id, scope.school_id)
            subject_id = exam_subject_id
        if not exam_id:
            return json.dumps({"error": "需要提供 exam_id 或 exam_subject_id"})
        if scope.visible_class_ids is not None and class_id and class_id not in scope.visible_class_ids:
            return json.dumps({"error": "无权访问该班级"})

        from edu_cloud.modules.analytics.service import exam_distribution
        scope_classes = [class_id] if class_id else scope.visible_class_ids
        data = await exam_distribution(
            db, exam_id=exam_id, school_id=scope.school_id,
            subject_id=subject_id,
            visible_subject_codes=scope.visible_subject_codes,
            visible_class_ids=scope_classes,
        )
    return json.dumps(data, ensure_ascii=False, default=str)


@edu_tool(name="get_question_analysis", module_code="study_analytics", domain="analytics", allowed_roles=_ANALYTICS_ROLES, sensitivity="school")
async def get_question_analysis(ctx: RunContext[AgentDeps], subject_id: str) -> str:
    """Get per-question score-rate analysis for a subject."""
    from edu_cloud.modules.analytics.service import subject_question_analysis

    scope = ctx.deps.data_scope
    async with ctx.deps.get_db() as db:
        data = await subject_question_analysis(
            db, subject_id=subject_id, school_id=scope.school_id,
            visible_subject_codes=scope.visible_subject_codes,
        )
    return json.dumps(data, ensure_ascii=False, default=str)


@edu_tool(name="get_student_scores", module_code="study_analytics", domain="analytics", allowed_roles=_ANALYTICS_ROLES, sensitivity="student")
async def get_student_scores(ctx: RunContext[AgentDeps], exam_id: str, student_id: str) -> str:
    """Get a student's detailed per-subject per-question scores for an exam."""
    from edu_cloud.modules.student.service import get_student
    from edu_cloud.modules.analytics.service import get_student_exam_scores

    scope = ctx.deps.data_scope
    async with ctx.deps.get_db() as db:
        student = await get_student(db, student_id=student_id, school_id=scope.school_id)
        if not student:
            return json.dumps({"error": "学生不存在"})
        if scope.visible_class_ids is not None and student.class_id not in scope.visible_class_ids:
            return json.dumps({"error": "无权查看该学生成绩"})
        all_scores = await get_student_exam_scores(
            db, exam_id=exam_id, student_id=student_id, school_id=scope.school_id,
        )
    total = sum(s["score"] for s in all_scores)
    total_max = sum(s["max_score"] for s in all_scores)
    return json.dumps({
        "student_id": student_id, "student_name": student.name,
        "total_score": total, "total_max": total_max, "details": all_scores,
    }, ensure_ascii=False, default=str)


@edu_tool(name="get_class_scores", module_code="study_analytics", domain="analytics", allowed_roles=_ANALYTICS_ROLES, sensitivity="student")
async def get_class_scores(
    ctx: RunContext[AgentDeps],
    class_id: str,
    exam_id: str | None = None,
    subject_id: str | None = None,
    exam_subject_id: str | None = None,
) -> str:
    """Get a class's student score list for an exam. Supports exam_subject_id shorthand."""
    from sqlalchemy import select
    from edu_cloud.modules.exam.models import Subject
    from edu_cloud.modules.student.models import Student
    from edu_cloud.modules.analytics.service import get_effective_scores

    scope = ctx.deps.data_scope
    if scope.visible_class_ids is not None and class_id not in scope.visible_class_ids:
        return json.dumps({"error": "无权访问该班级"})

    async with ctx.deps.get_db() as db:
        if exam_subject_id and not exam_id:
            from edu_cloud.modules.analytics.service import resolve_subject_to_exam
            exam_id, _ = await resolve_subject_to_exam(db, exam_subject_id, scope.school_id)
            subject_id = exam_subject_id
        if not exam_id:
            return json.dumps({"error": "需要提供 exam_id 或 exam_subject_id"})

        students = {s.id: s for s in (await db.execute(
            select(Student).where(Student.class_id == class_id, Student.school_id == scope.school_id)
        )).scalars().all()}

        subj_q = select(Subject).where(Subject.exam_id == exam_id, Subject.school_id == scope.school_id)
        if subject_id:
            subj_q = subj_q.where(Subject.id == subject_id)
        if scope.visible_subject_codes is not None:
            subj_q = subj_q.where(Subject.code.in_(scope.visible_subject_codes))
        subjects = (await db.execute(subj_q)).scalars().all()

        totals: dict[str, float] = {}
        for subj in subjects:
            scores = await get_effective_scores(db, subj.id, scope.school_id, [class_id])
            for s in scores:
                totals[s["student_id"]] = totals.get(s["student_id"], 0) + s["effective_score"]

    results = []
    for sid, total in sorted(totals.items(), key=lambda x: x[1], reverse=True):
        st = students.get(sid)
        results.append({"student_id": sid, "student_name": st.name if st else "", "total_score": total})
    return json.dumps({"class_id": class_id, "students": results}, ensure_ascii=False, default=str)


ALL_TOOLS = [get_exam_summary, get_score_distribution, get_question_analysis, get_student_scores, get_class_scores]
