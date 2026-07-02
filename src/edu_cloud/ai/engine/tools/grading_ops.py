"""Grading operations tools — Pydantic AI native (migrated from ai/tools/grading_ops.py)."""
from __future__ import annotations

import json

from pydantic_ai import RunContext

from edu_cloud.ai.engine.agent_deps import AgentDeps
from edu_cloud.ai.engine.tool_wrapper import edu_tool

_GRADING_READ_ROLES = frozenset({
    "platform_admin", "district_admin", "school_admin", "principal",
    "academic_director", "grade_leader",
    "homeroom_teacher", "subject_teacher",
})
_GRADING_WRITE_ROLES = frozenset({"platform_admin", "academic_director"})


@edu_tool(name="get_grading_progress", module_code="grading", domain="exam", allowed_roles=_GRADING_READ_ROLES, sensitivity="school")
async def get_grading_progress(ctx: RunContext[AgentDeps], exam_id: str) -> str:
    """Get grading progress summary for an exam."""
    from edu_cloud.modules.grading.service import GradingAssignmentService
    scope = ctx.deps.data_scope
    async with ctx.deps.get_db() as db:
        data = await GradingAssignmentService.get_progress(db, exam_id, school_id=scope.school_id)
    return json.dumps(data, ensure_ascii=False, default=str)


@edu_tool(name="get_quality_report", module_code="grading", domain="exam", allowed_roles=_GRADING_WRITE_ROLES, sensitivity="school")
async def get_quality_report(ctx: RunContext[AgentDeps], exam_id: str) -> str:
    """Get grading quality check report for an exam."""
    from edu_cloud.modules.grading.service import QualityCheckService
    scope = ctx.deps.data_scope
    async with ctx.deps.get_db() as db:
        data = await QualityCheckService.get_quality_report(db, exam_id, school_id=scope.school_id)
    return json.dumps(data, ensure_ascii=False, default=str)


@edu_tool(
    name="assign_grading_task", module_code="grading", domain="exam",
    allowed_roles=_GRADING_WRITE_ROLES, risk_level="medium", is_read_only=False, sensitivity="school",
)
async def assign_grading_task(
    ctx: RunContext[AgentDeps], exam_id: str, subject_id: str,
    question_ids: list[str], teacher_ids: list[str], total_count_per_question: int = 0,
) -> str:
    """Auto-assign grading tasks to teachers."""
    from edu_cloud.modules.grading.service import GradingAssignmentService
    scope = ctx.deps.data_scope
    async with ctx.deps.get_db() as db:
        result = await GradingAssignmentService.auto_assign(
            db,
            exam_id=exam_id,
            subject_id=subject_id,
            question_ids=question_ids,
            teacher_ids=teacher_ids,
            school_id=scope.school_id,
            total_count_per_question=total_count_per_question,
        )
    return json.dumps(result, ensure_ascii=False, default=str)


ALL_TOOLS = [get_grading_progress, get_quality_report, assign_grading_task]
