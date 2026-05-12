"""Analytics report tools — Pydantic AI native (migrated from ai/tools/analytics_report.py)."""
from __future__ import annotations

import json

from pydantic_ai import RunContext

from edu_cloud.ai.engine.agent_deps import AgentDeps
from edu_cloud.ai.engine.tool_wrapper import edu_tool

_REPORT_ROLES = frozenset({
    "platform_admin", "academic_director",
    "grade_leader", "homeroom_teacher",
})
_REPORT_WRITE_ROLES = frozenset({"platform_admin", "academic_director", "grade_leader"})


@edu_tool(name="get_score_segments", module_code="exam", domain="analytics", allowed_roles=_REPORT_ROLES, sensitivity="school")
async def get_score_segments(ctx: RunContext[AgentDeps], exam_id: str, subject_code: str | None = None) -> str:
    """Get score segment distribution with school-configured boundaries."""
    from edu_cloud.modules.analytics.segment_service import get_segment_config
    from edu_cloud.modules.analytics.service import exam_distribution
    scope = ctx.deps.data_scope
    async with ctx.deps.get_db() as db:
        config = await get_segment_config(db, scope.school_id, subject_code)
        data = await exam_distribution(
            db, exam_id=exam_id, school_id=scope.school_id,
            visible_subject_codes=scope.visible_subject_codes,
            visible_class_ids=scope.visible_class_ids,
        )
    return json.dumps({"config": config, "distribution": data}, ensure_ascii=False, default=str)


@edu_tool(name="compare_exams", module_code="exam", domain="analytics", allowed_roles=_REPORT_ROLES, sensitivity="school")
async def compare_exams(ctx: RunContext[AgentDeps], exam_ids: list[str], dimension: str = "grade") -> str:
    """Compare multiple exams over time (grade/class/student trend)."""
    from edu_cloud.modules.analytics.report_service import get_grade_trend, get_class_trend, get_student_trend
    scope = ctx.deps.data_scope
    async with ctx.deps.get_db() as db:
        if dimension == "class":
            data = await get_class_trend(db, exam_ids, scope.school_id, scope.visible_class_ids)
        elif dimension == "student":
            data = await get_student_trend(db, exam_ids, scope.school_id, scope.visible_class_ids)
        else:
            data = await get_grade_trend(db, exam_ids, scope.school_id)
    return json.dumps(data, ensure_ascii=False, default=str)


@edu_tool(
    name="generate_analysis_report", module_code="exam", domain="analytics",
    allowed_roles=_REPORT_WRITE_ROLES, risk_level="medium", is_read_only=False, sensitivity="school",
)
async def generate_analysis_report(ctx: RunContext[AgentDeps], exam_ids: list[str], title: str = "成绩分析报告") -> str:
    """Generate a comprehensive analysis report document."""
    from edu_cloud.modules.analytics.report_service import build_report
    scope = ctx.deps.data_scope
    async with ctx.deps.get_db() as db:
        report = await build_report(
            db, school_id=scope.school_id, exam_ids=exam_ids,
            visible_subject_codes=scope.visible_subject_codes,
            visible_class_ids=scope.visible_class_ids,
        )
    return json.dumps({"status": "ok", "title": title, "report_summary": str(report)[:500]}, ensure_ascii=False, default=str)


ALL_TOOLS = [get_score_segments, compare_exams, generate_analysis_report]
