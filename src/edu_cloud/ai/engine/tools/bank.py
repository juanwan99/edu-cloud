"""Question bank tools — Pydantic AI native (migrated from ai/tools/bank.py)."""
from __future__ import annotations

import json

from pydantic_ai import RunContext

from edu_cloud.ai.engine.agent_deps import AgentDeps
from edu_cloud.ai.engine.tool_wrapper import edu_tool

_BANK_ROLES = frozenset({
    "platform_admin", "academic_director", "grade_leader",
    "homeroom_teacher", "subject_teacher", "parent",
})


@edu_tool(name="get_student_error_book", module_code="exam", domain="bank", allowed_roles=_BANK_ROLES, sensitivity="student")
async def get_student_error_book(ctx: RunContext[AgentDeps], student_id: str, mastery_status: str | None = None) -> str:
    """Get a student's error book (wrong answers) with optional mastery filter."""
    from edu_cloud.modules.bank.service import get_student_error_book as svc, get_error_book_stats
    scope = ctx.deps.data_scope
    async with ctx.deps.get_db() as db:
        errors = await svc(db, student_id=student_id, school_id=scope.school_id, mastery_status=mastery_status)
        stats = await get_error_book_stats(db, student_id=student_id, school_id=scope.school_id)
    return json.dumps({"errors": errors, "stats": stats}, ensure_ascii=False, default=str)


@edu_tool(name="get_question_stats", module_code="exam", domain="bank", allowed_roles=_BANK_ROLES, sensitivity="student")
async def get_question_stats(ctx: RunContext[AgentDeps], bank_question_id: str) -> str:
    """Get statistics for a question in the question bank."""
    from edu_cloud.modules.bank.service import get_bank_question
    scope = ctx.deps.data_scope
    async with ctx.deps.get_db() as db:
        data = await get_bank_question(db, bank_question_id=bank_question_id, school_id=scope.school_id)
    return json.dumps(data, ensure_ascii=False, default=str)


ALL_TOOLS = [get_student_error_book, get_question_stats]
