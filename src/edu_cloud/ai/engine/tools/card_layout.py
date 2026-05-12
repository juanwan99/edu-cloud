"""Card layout tools — Pydantic AI native (migrated from ai/tools/card_layout.py).

Note: card_auto_layout and card_adjust_layout contain complex layout logic
that depends on helper functions. Those helpers are left in the old module
and imported from there until the full card module is refactored.
"""
from __future__ import annotations

import json

from pydantic_ai import RunContext

from edu_cloud.ai.engine.agent_deps import AgentDeps
from edu_cloud.ai.engine.tool_wrapper import edu_tool

_CARD_ROLES = frozenset({
    "platform_admin", "academic_director",
    "homeroom_teacher", "subject_teacher",
})


@edu_tool(name="card_parse_answers", module_code="card", domain="exam", allowed_roles=_CARD_ROLES, sensitivity="school")
async def card_parse_answers(ctx: RunContext[AgentDeps], file_path: str) -> str:
    """Parse answer document to extract question answers."""
    from edu_cloud.modules.card.parser.answer_parser import parse_answer_docx
    result = await parse_answer_docx(file_path)
    return json.dumps(result, ensure_ascii=False, default=str)


@edu_tool(
    name="card_auto_layout", module_code="card", domain="exam",
    allowed_roles=_CARD_ROLES, is_read_only=False, sensitivity="school",
)
async def card_auto_layout(ctx: RunContext[AgentDeps], subject_id: str) -> str:
    """Auto-calculate answer card layout based on questions."""
    from edu_cloud.ai.tools.card_layout import card_auto_layout as legacy_fn
    from edu_cloud.ai.tool_context import ToolContext
    scope = ctx.deps.data_scope
    async with ctx.deps.get_db() as db:
        legacy_ctx = ToolContext(db=db, school_id=scope.school_id, user_id=ctx.deps.user_id, role=ctx.deps.role)
        result = await legacy_fn({"subject_id": subject_id}, legacy_ctx)
    return json.dumps(result.to_dict(), ensure_ascii=False, default=str)


@edu_tool(
    name="card_adjust_layout", module_code="card", domain="exam",
    allowed_roles=_CARD_ROLES, is_read_only=False, sensitivity="school",
)
async def card_adjust_layout(ctx: RunContext[AgentDeps], subject_id: str, adjustments: dict | None = None) -> str:
    """Adjust existing answer card layout."""
    from edu_cloud.ai.tools.card_layout import card_adjust_layout as legacy_fn
    from edu_cloud.ai.tool_context import ToolContext
    scope = ctx.deps.data_scope
    async with ctx.deps.get_db() as db:
        legacy_ctx = ToolContext(db=db, school_id=scope.school_id, user_id=ctx.deps.user_id, role=ctx.deps.role)
        result = await legacy_fn({"subject_id": subject_id, **(adjustments or {})}, legacy_ctx)
    return json.dumps(result.to_dict(), ensure_ascii=False, default=str)


ALL_TOOLS = [card_parse_answers, card_auto_layout, card_adjust_layout]
