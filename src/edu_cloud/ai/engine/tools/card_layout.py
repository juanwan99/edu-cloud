"""Card layout tools — Pydantic AI native.

Uses layout_helpers directly, no old engine dependency.
"""
from __future__ import annotations

import json

from pydantic_ai import RunContext
from sqlalchemy import select

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
async def card_auto_layout(
    ctx: RunContext[AgentDeps], subject_id: str, parsed_questions: list[dict] | None = None,
) -> str:
    """Auto-calculate answer card layout based on questions."""
    from edu_cloud.modules.card.layout_helpers import (
        calculate_layout, _load_layout, _apply_to_regions, _save_layout,
    )
    from edu_cloud.modules.exam.models import Subject

    school_id = ctx.deps.data_scope.school_id
    async with ctx.deps.get_db() as db:
        subject = (await db.execute(
            select(Subject).where(Subject.id == subject_id, Subject.school_id == school_id)
        )).scalar_one_or_none()
        if not subject:
            return json.dumps({"success": False, "error": "科目不存在"})

    if not parsed_questions:
        return json.dumps({"success": False, "error": "需要 parsed_questions 参数"})

    layout = _load_layout(school_id, subject_id, subject.name)
    layout_result = calculate_layout(parsed_questions, layout.get("config"), existing_layout=layout)
    layout = _apply_to_regions(layout, layout_result)
    _save_layout(school_id, subject_id, layout)

    return json.dumps({"success": True, "layout": layout_result}, ensure_ascii=False, default=str)


@edu_tool(
    name="card_adjust_layout", module_code="card", domain="exam",
    allowed_roles=_CARD_ROLES, is_read_only=False, sensitivity="school",
)
async def card_adjust_layout(ctx: RunContext[AgentDeps], subject_id: str, adjustments: list[dict] | None = None) -> str:
    """Adjust existing answer card layout."""
    from edu_cloud.modules.card.layout_helpers import (
        _load_layout, _save_layout, BLANK_SHORT, BLANK_MEDIUM, BLANK_LONG,
    )
    from edu_cloud.modules.exam.models import Subject

    school_id = ctx.deps.data_scope.school_id
    async with ctx.deps.get_db() as db:
        subject = (await db.execute(
            select(Subject).where(Subject.id == subject_id, Subject.school_id == school_id)
        )).scalar_one_or_none()
        if not subject:
            return json.dumps({"success": False, "error": "科目不存在"})

    layout = _load_layout(school_id, subject_id, subject.name)

    regions = {}
    for side in layout.get("sides", []):
        for col in side.get("columns", []):
            for r in col.get("regions", []):
                if r.get("type") == "essay" and r.get("qno"):
                    regions[r["qno"]] = r

    width_map = {"short": BLANK_SHORT, "medium": BLANK_MEDIUM, "long": BLANK_LONG}
    changes = []

    for adj in (adjustments or []):
        action = adj.get("action", "")
        if action == "resize":
            qno = adj.get("qno")
            delta = adj.get("delta", 0.05)
            if qno in regions:
                old = regions[qno]["heightRatio"]
                regions[qno]["heightRatio"] = round(max(0.05, old + delta), 4)
                changes.append(f"Q{qno} {old:.0%}→{regions[qno]['heightRatio']:.0%}")
        elif action == "set_blank_width":
            qno = adj.get("qno")
            si = (adj.get("sub", 1) or 1) - 1
            bi = adj.get("blank_index", 0) or 0
            w = width_map.get(adj.get("width", "long"), BLANK_LONG)
            if qno in regions:
                subs = regions[qno].get("subs", [])
                if si < len(subs) and bi < len(subs[si].get("blanks", [])):
                    subs[si]["blanks"][bi]["w"] = w
                    changes.append(f"Q{qno}({si+1})空{bi+1}→{adj.get('width')}")
        elif action == "balance":
            q1, q2 = adj.get("qno"), adj.get("qno2")
            if q1 in regions and q2 in regions:
                avg = (regions[q1]["heightRatio"] + regions[q2]["heightRatio"]) / 2
                regions[q1]["heightRatio"] = regions[q2]["heightRatio"] = round(avg, 4)
                changes.append(f"Q{q1}+Q{q2}均衡→{avg:.0%}")

    total = sum(r["heightRatio"] for r in regions.values())
    if total > 0:
        for r in regions.values():
            r["heightRatio"] = round(r["heightRatio"] / total, 4)

    _save_layout(school_id, subject_id, layout)
    return json.dumps({"success": True, "changes": changes}, ensure_ascii=False, default=str)


ALL_TOOLS = [card_parse_answers, card_auto_layout, card_adjust_layout]
