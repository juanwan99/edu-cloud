"""Findings & tasks domain tools — read-only access to AgentFinding / AgentTask."""
import logging

from sqlalchemy import select

from edu_cloud.ai.registry import tools
from edu_cloud.ai.tool_context import ToolContext, ToolResult
from edu_cloud.models.agent_finding import AgentFinding, AgentTask

logger = logging.getLogger(__name__)


@tools.register(
    name="get_findings",
    description="查询 Agent 巡检发现列表（按学校隔离），支持按状态过滤。",
    parameters={
        "type": "object",
        "properties": {
            "status": {
                "type": "string",
                "description": "按状态过滤（new/notified/resolved）",
            },
            "limit": {
                "type": "integer",
                "description": "返回条数上限（默认 20，最大 50）",
            },
        },
        "required": [],
    },
    category="analytics",
    domain="agent_finding",
    allowed_roles=[
        "platform_admin", "district_admin", "principal",
        "academic_director", "grade_leader", "homeroom_teacher", "subject_teacher",
    ],
    risk_level="low",
    is_read_only=True,
)
async def get_findings(input: dict, ctx: ToolContext) -> ToolResult:
    limit = min(input.get("limit", 20), 50)
    status = input.get("status")

    try:
        stmt = (
            select(AgentFinding)
            .where(AgentFinding.school_id == ctx.school_id)
            .order_by(AgentFinding.created_at.desc())
            .limit(limit)
        )
        if status:
            stmt = stmt.where(AgentFinding.status == status)

        result = await ctx.db.execute(stmt)
        findings = result.scalars().all()

        return ToolResult(
            success=True,
            data={
                "findings": [
                    {
                        "id": f.id,
                        "finding_type": f.finding_type,
                        "severity": f.severity,
                        "target_type": f.target_type,
                        "target_id": f.target_id,
                        "summary": f.summary,
                        "status": f.status,
                        "created_at": str(f.created_at) if f.created_at else None,
                    }
                    for f in findings
                ],
            },
        )
    except Exception as e:
        logger.exception("get_findings failed")
        return ToolResult(success=False, error=str(e))


@tools.register(
    name="get_agent_tasks",
    description="查询 Agent 生成的待办任务列表（按学校隔离），支持按状态过滤。",
    parameters={
        "type": "object",
        "properties": {
            "status": {
                "type": "string",
                "description": "按状态过滤（pending/done）",
            },
            "limit": {
                "type": "integer",
                "description": "返回条数上限（默认 20）",
            },
        },
        "required": [],
    },
    category="analytics",
    domain="agent_task",
    allowed_roles=[
        "platform_admin", "district_admin", "principal",
        "academic_director", "grade_leader", "homeroom_teacher", "subject_teacher",
    ],
    risk_level="low",
    is_read_only=True,
)
async def get_agent_tasks(input: dict, ctx: ToolContext) -> ToolResult:
    limit = min(input.get("limit", 20), 50)
    status = input.get("status")

    try:
        stmt = (
            select(AgentTask)
            .where(AgentTask.school_id == ctx.school_id)
            .order_by(AgentTask.created_at.desc())
            .limit(limit)
        )
        if status:
            stmt = stmt.where(AgentTask.status == status)

        result = await ctx.db.execute(stmt)
        tasks = result.scalars().all()

        return ToolResult(
            success=True,
            data={
                "tasks": [
                    {
                        "id": t.id,
                        "finding_id": t.finding_id,
                        "task_type": t.task_type,
                        "assignee_role": t.assignee_role,
                        "status": t.status,
                        "payload": t.payload,
                        "created_at": str(t.created_at) if t.created_at else None,
                    }
                    for t in tasks
                ],
            },
        )
    except Exception as e:
        logger.exception("get_agent_tasks failed")
        return ToolResult(success=False, error=str(e))
