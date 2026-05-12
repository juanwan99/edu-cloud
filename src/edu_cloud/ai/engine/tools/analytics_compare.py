"""Comparison analytics tools — Pydantic AI native (migrated from ai/tools/analytics_compare.py)."""
from __future__ import annotations

import json
import statistics as stats_mod

from pydantic_ai import RunContext
from sqlalchemy import select

from edu_cloud.ai.engine.agent_deps import AgentDeps
from edu_cloud.ai.engine.tool_wrapper import edu_tool

_ANALYTICS_ROLES = frozenset({"platform_admin", "academic_director", "grade_leader"})


async def _resolve_exam_subject(db, exam_subject_id, exam_id, school_id):
    if exam_subject_id and not exam_id:
        from edu_cloud.modules.analytics.service import resolve_subject_to_exam
        exam_id, _ = await resolve_subject_to_exam(db, exam_subject_id, school_id)
        return exam_id, exam_subject_id
    return exam_id, None


@edu_tool(name="compare_classes", module_code="exam", domain="analytics", allowed_roles=_ANALYTICS_ROLES, sensitivity="school")
async def compare_classes(
    ctx: RunContext[AgentDeps],
    class_ids: list[str],
    exam_id: str | None = None,
    subject_id: str | None = None,
    exam_subject_id: str | None = None,
) -> str:
    """Compare scores across multiple classes. Returns per-class avg/max/min."""
    from edu_cloud.modules.exam.models import Subject
    from edu_cloud.modules.analytics.service import get_effective_scores

    scope = ctx.deps.data_scope
    async with ctx.deps.get_db() as db:
        exam_id, resolved_subj = await _resolve_exam_subject(db, exam_subject_id, exam_id, scope.school_id)
        if resolved_subj:
            subject_id = resolved_subj
        if not exam_id:
            return json.dumps({"error": "需要提供 exam_id 或 exam_subject_id"})

        allowed_ids = class_ids
        filtered_out = []
        if scope.visible_class_ids is not None:
            allowed_ids = [c for c in class_ids if c in scope.visible_class_ids]
            filtered_out = [c for c in class_ids if c not in scope.visible_class_ids]

        subj_q = select(Subject).where(Subject.exam_id == exam_id, Subject.school_id == scope.school_id)
        if subject_id:
            subj_q = subj_q.where(Subject.id == subject_id)
        if scope.visible_subject_codes is not None:
            subj_q = subj_q.where(Subject.code.in_(scope.visible_subject_codes))
        subjects = (await db.execute(subj_q)).scalars().all()

        comparisons = []
        for cid in allowed_ids:
            totals: dict[str, float] = {}
            for subj in subjects:
                scores = await get_effective_scores(db, subj.id, scope.school_id, [cid])
                for s in scores:
                    totals[s["student_id"]] = totals.get(s["student_id"], 0) + s["effective_score"]
            values = list(totals.values())
            if values:
                comparisons.append({"class_id": cid, "count": len(values), "avg": round(sum(values) / len(values), 2), "max": max(values), "min": min(values)})
            else:
                comparisons.append({"class_id": cid, "count": 0, "avg": None, "max": None, "min": None})

    data: dict = {"exam_id": exam_id, "comparisons": comparisons}
    if filtered_out:
        data["warning"] = f"以下班级无权访问: {filtered_out}"
    return json.dumps(data, ensure_ascii=False, default=str)


@edu_tool(name="rank_students", module_code="exam", domain="analytics", allowed_roles=_ANALYTICS_ROLES, sensitivity="student")
async def rank_students(
    ctx: RunContext[AgentDeps],
    exam_id: str | None = None,
    subject_id: str | None = None,
    exam_subject_id: str | None = None,
    class_id: str | None = None,
    top_n: int = 20,
) -> str:
    """Student ranking table. Filter by subject/class, return top N."""
    from edu_cloud.modules.exam.models import Subject
    from edu_cloud.modules.student.models import Student
    from edu_cloud.modules.analytics.service import get_effective_scores

    scope = ctx.deps.data_scope
    async with ctx.deps.get_db() as db:
        exam_id, resolved_subj = await _resolve_exam_subject(db, exam_subject_id, exam_id, scope.school_id)
        if resolved_subj:
            subject_id = resolved_subj
        if not exam_id:
            return json.dumps({"error": "需要提供 exam_id 或 exam_subject_id"})
        if scope.visible_class_ids is not None and class_id and class_id not in scope.visible_class_ids:
            return json.dumps({"error": "无权访问该班级"})

        scope_classes = [class_id] if class_id else scope.visible_class_ids
        subj_q = select(Subject).where(Subject.exam_id == exam_id, Subject.school_id == scope.school_id)
        if subject_id:
            subj_q = subj_q.where(Subject.id == subject_id)
        if scope.visible_subject_codes is not None:
            subj_q = subj_q.where(Subject.code.in_(scope.visible_subject_codes))
        subjects = (await db.execute(subj_q)).scalars().all()

        totals: dict[str, float] = {}
        for subj in subjects:
            scores = await get_effective_scores(db, subj.id, scope.school_id, scope_classes)
            for s in scores:
                totals[s["student_id"]] = totals.get(s["student_id"], 0) + s["effective_score"]

        ranked = sorted(totals.items(), key=lambda x: x[1], reverse=True)[:top_n]
        student_ids = [sid for sid, _ in ranked]
        students = {}
        if student_ids:
            students = {s.id: s for s in (await db.execute(
                select(Student).where(Student.id.in_(student_ids), Student.school_id == scope.school_id)
            )).scalars().all()}

    results = [
        {"rank": r, "student_id": sid, "student_name": students.get(sid, type("", (), {"name": ""})).name, "total_score": total}
        for r, (sid, total) in enumerate(ranked, 1)
    ]
    return json.dumps({"ranking": results}, ensure_ascii=False, default=str)


@edu_tool(name="get_grade_aggregates", module_code="exam", domain="analytics", allowed_roles=_ANALYTICS_ROLES, sensitivity="school")
async def get_grade_aggregates(
    ctx: RunContext[AgentDeps],
    exam_id: str | None = None,
    subject_id: str | None = None,
    exam_subject_id: str | None = None,
) -> str:
    """Grade-level aggregate statistics (avg/median/stdev). K-anonymity: groups < 5 suppressed."""
    from edu_cloud.modules.exam.models import Subject
    from edu_cloud.modules.analytics.service import get_effective_scores

    scope = ctx.deps.data_scope
    async with ctx.deps.get_db() as db:
        exam_id, resolved_subj = await _resolve_exam_subject(db, exam_subject_id, exam_id, scope.school_id)
        if resolved_subj:
            subject_id = resolved_subj
        if not exam_id:
            return json.dumps({"error": "需要提供 exam_id 或 exam_subject_id"})

        subj_q = select(Subject).where(Subject.exam_id == exam_id, Subject.school_id == scope.school_id)
        if subject_id:
            subj_q = subj_q.where(Subject.id == subject_id)
        if scope.visible_subject_codes is not None:
            subj_q = subj_q.where(Subject.code.in_(scope.visible_subject_codes))
        subjects = (await db.execute(subj_q)).scalars().all()

        totals: dict[str, float] = {}
        for subj in subjects:
            scores = await get_effective_scores(db, subj.id, scope.school_id)
            for s in scores:
                totals[s["student_id"]] = totals.get(s["student_id"], 0) + s["effective_score"]

    values = list(totals.values())
    if len(values) < 5:
        return json.dumps({"error": "人数不足 5，不返回聚合统计"})
    return json.dumps({
        "exam_id": exam_id, "count": len(values),
        "avg": round(sum(values) / len(values), 2),
        "median": round(stats_mod.median(values), 2),
        "stdev": round(stats_mod.stdev(values), 2) if len(values) > 1 else 0,
        "max": max(values), "min": min(values),
    }, ensure_ascii=False, default=str)


ALL_TOOLS = [compare_classes, rank_students, get_grade_aggregates]
