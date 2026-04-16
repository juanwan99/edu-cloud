"""Agent 工具 — 操行/德育积分查询与操作（6 tools）。

F003 Hardening: 每个工具先通过 class_ids / student.class_id 与 ctx.class_ids 做交集校验，
避免 AI 绕过 DataScope 跨班读写。校级+ 角色的 ctx.class_ids 为 None = 全可见。
"""
import logging
from datetime import date, timedelta

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from edu_cloud.ai.registry import tools
from edu_cloud.ai.tool_context import ToolContext, ToolResult
from edu_cloud.modules.conduct.models import (
    ConductRecord, ConductRuleCategory, ConductRuleItem,
)
from edu_cloud.modules.student.models import Student

logger = logging.getLogger(__name__)


# ── F003: scope 校验辅助 ──

def _check_class_in_scope(ctx: ToolContext, class_id: str) -> str | None:
    """校验 class_id 是否在 ctx.class_ids 中。

    Returns: None 表示通过；非 None 表示错误消息。
    """
    if ctx.class_ids is None:
        return None  # None = 校级以上，全可见
    if class_id not in ctx.class_ids:
        return f"class '{class_id}' out of scope for role {ctx.role}"
    return None


async def _check_student_in_scope(
    ctx: ToolContext, student_id: str,
) -> tuple[Student | None, str | None]:
    """校验 student 的 class_id 是否在 ctx.class_ids 中。

    Returns: (student, error_msg). error_msg 非 None 表示越权。
    """
    student = (
        await ctx.db.execute(select(Student).where(Student.id == student_id))
    ).scalar_one_or_none()
    if student is None:
        return None, f"student '{student_id}' not found"
    if ctx.class_ids is None:
        return student, None
    if student.class_id not in ctx.class_ids:
        return student, f"student '{student_id}' out of scope for role {ctx.role}"
    return student, None


# ═══════════════════════════════════════════════════
# 1. get_conduct_rankings — 班级积分排行榜
# ═══════════════════════════════════════════════════

@tools.register(
    name="get_conduct_rankings",
    description="获取班级操行积分排行榜，按总积分降序排列（TOP 20）。支持按时间段筛选：全部/本周/本月。",
    parameters={
        "type": "object",
        "properties": {
            "class_id": {"type": "string", "description": "班级 ID"},
            "period": {
                "type": "string",
                "description": "时间段：all（默认）/ this_week / this_month",
                "enum": ["all", "this_week", "this_month"],
            },
        },
        "required": ["class_id"],
    },
    category="L2_conduct",
    module_code="conduct",
    domain="L2_conduct",
    risk_level="low",
    is_read_only=True,
    sensitivity="school",
)
async def get_conduct_rankings(input: dict, ctx: ToolContext) -> ToolResult:
    class_id = input.get("class_id", "")
    period = input.get("period", "all")
    scope_err = _check_class_in_scope(ctx, class_id)
    if scope_err:
        return ToolResult(success=False, error=scope_err)
    try:
        stmt = (
            select(
                Student.id,
                Student.name,
                Student.student_number,
                func.coalesce(func.sum(ConductRecord.points), 0).label("total"),
            )
            .outerjoin(ConductRecord, ConductRecord.student_id == Student.id)
            .where(Student.class_id == class_id)
        )

        if period == "this_week":
            since = date.today() - timedelta(days=7)
            stmt = stmt.where(
                (ConductRecord.date >= since) | (ConductRecord.id.is_(None))
            )
        elif period == "this_month":
            since = date.today() - timedelta(days=30)
            stmt = stmt.where(
                (ConductRecord.date >= since) | (ConductRecord.id.is_(None))
            )

        stmt = (
            stmt
            .group_by(Student.id, Student.name, Student.student_number)
            .order_by(func.coalesce(func.sum(ConductRecord.points), 0).desc())
            .limit(20)
        )

        rows = (await ctx.db.execute(stmt)).all()
        rankings = []
        for rank, row in enumerate(rows, 1):
            rankings.append({
                "rank": rank,
                "student_id": row[0],
                "name": row[1],
                "student_number": row[2],
                "total_points": int(row[3]),
            })

        return ToolResult(success=True, data={
            "class_id": class_id,
            "period": period,
            "rankings": rankings,
        })
    except Exception as e:
        logger.exception("get_conduct_rankings failed")
        return ToolResult(success=False, error=str(e))


# ═══════════════════════════════════════════════════
# 2. get_student_conduct_summary — 学生操行概览
# ═══════════════════════════════════════════════════

@tools.register(
    name="get_student_conduct_summary",
    description="获取单个学生的操行概览：总积分、分类汇总、最近 5 条记录。",
    parameters={
        "type": "object",
        "properties": {
            "student_id": {"type": "string", "description": "学生 ID"},
        },
        "required": ["student_id"],
    },
    category="L6_profile",
    module_code="conduct",
    domain="L6_profile",
    risk_level="low",
    is_read_only=True,
    sensitivity="student",
)
async def get_student_conduct_summary(input: dict, ctx: ToolContext) -> ToolResult:
    student_id = input.get("student_id", "")
    student, scope_err = await _check_student_in_scope(ctx, student_id)
    if scope_err:
        return ToolResult(success=False, error=scope_err)
    try:
        # Total points
        total_row = (await ctx.db.execute(
            select(func.coalesce(func.sum(ConductRecord.points), 0))
            .where(ConductRecord.student_id == student_id)
        )).scalar()
        total_points = int(total_row or 0)

        # Category breakdown via rule_item -> category
        cat_stmt = (
            select(
                ConductRuleCategory.name.label("category_name"),
                func.sum(ConductRecord.points).label("cat_total"),
            )
            .join(ConductRuleItem, ConductRecord.rule_item_id == ConductRuleItem.id)
            .join(ConductRuleCategory, ConductRuleItem.category_id == ConductRuleCategory.id)
            .where(ConductRecord.student_id == student_id)
            .group_by(ConductRuleCategory.name)
        )
        cat_rows = (await ctx.db.execute(cat_stmt)).all()
        categories = [
            {"category": row.category_name, "points": int(row.cat_total)}
            for row in cat_rows
        ]

        # Uncategorized (records without rule_item_id)
        uncat = (await ctx.db.execute(
            select(func.coalesce(func.sum(ConductRecord.points), 0))
            .where(
                ConductRecord.student_id == student_id,
                ConductRecord.rule_item_id.is_(None),
            )
        )).scalar()
        if uncat and int(uncat) != 0:
            categories.append({"category": "未分类", "points": int(uncat)})

        # Recent 5 records
        recent_stmt = (
            select(ConductRecord)
            .where(ConductRecord.student_id == student_id)
            .order_by(ConductRecord.date.desc(), ConductRecord.created_at.desc())
            .limit(5)
        )
        recent_rows = (await ctx.db.execute(recent_stmt)).scalars().all()
        recent = [
            {
                "date": str(r.date),
                "points": r.points,
                "reason": r.reason,
                "source": r.source,
            }
            for r in recent_rows
        ]

        return ToolResult(success=True, data={
            "student_id": student_id,
            "total_points": total_points,
            "categories": categories,
            "recent_records": recent,
        })
    except Exception as e:
        logger.exception("get_student_conduct_summary failed")
        return ToolResult(success=False, error=str(e))


# ═══════════════════════════════════════════════════
# 3. get_conduct_records — 查询积分记录
# ═══════════════════════════════════════════════════

@tools.register(
    name="get_conduct_records",
    description="查询班级操行积分记录（最近 N 天），可按学生筛选。",
    parameters={
        "type": "object",
        "properties": {
            "class_id": {"type": "string", "description": "班级 ID"},
            "student_id": {"type": "string", "description": "学生 ID（可选，筛选单个学生）"},
            "days": {"type": "integer", "description": "查询天数（默认 30）", "default": 30},
        },
        "required": ["class_id"],
    },
    category="L2_conduct",
    module_code="conduct",
    domain="L2_conduct",
    risk_level="low",
    is_read_only=True,
    sensitivity="school",
)
async def get_conduct_records(input: dict, ctx: ToolContext) -> ToolResult:
    class_id = input.get("class_id", "")
    student_id = input.get("student_id")
    days = input.get("days", 30)
    scope_err = _check_class_in_scope(ctx, class_id)
    if scope_err:
        return ToolResult(success=False, error=scope_err)
    try:
        since = date.today() - timedelta(days=days)
        stmt = (
            select(ConductRecord, Student.name.label("student_name"))
            .join(Student, ConductRecord.student_id == Student.id)
            .where(ConductRecord.class_id == class_id)
            .where(ConductRecord.date >= since)
            .order_by(ConductRecord.date.desc(), ConductRecord.created_at.desc())
            .limit(50)
        )
        if student_id:
            stmt = stmt.where(ConductRecord.student_id == student_id)

        rows = (await ctx.db.execute(stmt)).all()
        records = []
        for row in rows:
            record = row[0]
            records.append({
                "id": record.id,
                "student_id": record.student_id,
                "student_name": row.student_name,
                "points": record.points,
                "reason": record.reason,
                "date": str(record.date),
                "source": record.source,
            })

        return ToolResult(success=True, data={
            "class_id": class_id,
            "days": days,
            "records": records,
        })
    except Exception as e:
        logger.exception("get_conduct_records failed")
        return ToolResult(success=False, error=str(e))


# ═══════════════════════════════════════════════════
# 4. add_conduct_points — 添加积分
# ═══════════════════════════════════════════════════

@tools.register(
    name="add_conduct_points",
    description="给学生添加操行积分（加分或扣分），通过学生姓名查找。",
    parameters={
        "type": "object",
        "properties": {
            "student_name": {"type": "string", "description": "学生姓名"},
            "class_id": {"type": "string", "description": "班级 ID（可选，从上下文推断）"},
            "points": {"type": "integer", "description": "积分值（正数加分，负数扣分）"},
            "reason": {"type": "string", "description": "加/扣分原因"},
        },
        "required": ["student_name", "points", "reason"],
    },
    category="L2_conduct",
    module_code="conduct",
    domain="L2_conduct",
    risk_level="medium",
    is_read_only=False,
    sensitivity="school",
    allowed_roles=["homeroom_teacher", "subject_teacher", "academic_director"],
)
async def add_conduct_points(input: dict, ctx: ToolContext) -> ToolResult:
    student_name = input.get("student_name", "")
    class_id = input.get("class_id") or (ctx.class_ids[0] if ctx.class_ids else None)
    points = input.get("points", 0)
    reason = input.get("reason", "")

    if not class_id:
        return ToolResult(success=False, error="未指定班级，请提供 class_id")
    if not student_name:
        return ToolResult(success=False, error="未指定学生姓名")
    if not reason:
        return ToolResult(success=False, error="未填写原因")

    scope_err = _check_class_in_scope(ctx, class_id)
    if scope_err:
        return ToolResult(success=False, error=scope_err)

    try:
        # Find student by name in class
        stmt = select(Student).where(
            Student.name == student_name,
            Student.class_id == class_id,
        )
        student = (await ctx.db.execute(stmt)).scalar_one_or_none()
        if not student:
            return ToolResult(success=False, error=f"在该班级未找到名为「{student_name}」的学生")

        record = ConductRecord(
            student_id=student.id,
            class_id=class_id,
            points=points,
            reason=reason,
            date=date.today(),
            operator_id=ctx.user_id,
            source="agent",
        )
        ctx.db.add(record)
        await ctx.db.commit()
        await ctx.db.refresh(record)

        return ToolResult(success=True, data={
            "record_id": record.id,
            "student_name": student.name,
            "points": points,
            "reason": reason,
            "date": str(record.date),
        }, is_read_only=False)
    except Exception as e:
        logger.exception("add_conduct_points failed")
        return ToolResult(success=False, error=str(e))


# ═══════════════════════════════════════════════════
# 5. get_conduct_rules — 查询班规
# ═══════════════════════════════════════════════════

@tools.register(
    name="get_conduct_rules",
    description="获取班级班规列表（分类 + 条目嵌套结构）。",
    parameters={
        "type": "object",
        "properties": {
            "class_id": {"type": "string", "description": "班级 ID"},
        },
        "required": ["class_id"],
    },
    category="L2_conduct",
    module_code="conduct",
    domain="L2_conduct",
    risk_level="low",
    is_read_only=True,
    sensitivity="school",
)
async def get_conduct_rules(input: dict, ctx: ToolContext) -> ToolResult:
    class_id = input.get("class_id", "")
    scope_err = _check_class_in_scope(ctx, class_id)
    if scope_err:
        return ToolResult(success=False, error=scope_err)
    try:
        from edu_cloud.modules.conduct.rules_service import get_rules
        rules = await get_rules(ctx.db, class_id)
        return ToolResult(success=True, data={"class_id": class_id, "rules": rules})
    except Exception as e:
        logger.exception("get_conduct_rules failed")
        return ToolResult(success=False, error=str(e))


# ═══════════════════════════════════════════════════
# 6. get_class_conduct_overview — 班级操行概览
# ═══════════════════════════════════════════════════

@tools.register(
    name="get_class_conduct_overview",
    description="获取班级操行概览：学生人数、本周加扣分统计、积分最高/最低学生。",
    parameters={
        "type": "object",
        "properties": {
            "class_id": {"type": "string", "description": "班级 ID"},
        },
        "required": ["class_id"],
    },
    category="L2_conduct",
    module_code="conduct",
    domain="L2_conduct",
    risk_level="low",
    is_read_only=True,
    sensitivity="school",
)
async def get_class_conduct_overview(input: dict, ctx: ToolContext) -> ToolResult:
    class_id = input.get("class_id", "")
    scope_err = _check_class_in_scope(ctx, class_id)
    if scope_err:
        return ToolResult(success=False, error=scope_err)
    try:
        # Student count
        student_count = (await ctx.db.execute(
            select(func.count(Student.id)).where(Student.class_id == class_id)
        )).scalar() or 0

        # This week stats
        week_start = date.today() - timedelta(days=7)
        week_records_stmt = (
            select(ConductRecord.points)
            .where(
                ConductRecord.class_id == class_id,
                ConductRecord.date >= week_start,
            )
        )
        week_points = (await ctx.db.execute(week_records_stmt)).scalars().all()

        total_plus = sum(p for p in week_points if p > 0)
        total_minus = sum(p for p in week_points if p < 0)
        record_count = len(week_points)

        # Top / bottom students (all time)
        ranking_stmt = (
            select(
                Student.name,
                func.coalesce(func.sum(ConductRecord.points), 0).label("total"),
            )
            .outerjoin(ConductRecord, ConductRecord.student_id == Student.id)
            .where(Student.class_id == class_id)
            .group_by(Student.id, Student.name)
            .order_by(func.coalesce(func.sum(ConductRecord.points), 0).desc())
        )
        ranking_rows = (await ctx.db.execute(ranking_stmt)).all()

        top_students = [
            {"name": r[0], "total_points": int(r[1])}
            for r in ranking_rows[:3]
        ]
        bottom_students = [
            {"name": r[0], "total_points": int(r[1])}
            for r in ranking_rows[-3:]
        ] if len(ranking_rows) > 3 else []

        return ToolResult(success=True, data={
            "class_id": class_id,
            "student_count": student_count,
            "this_week": {
                "total_plus": total_plus,
                "total_minus": total_minus,
                "record_count": record_count,
            },
            "top_students": top_students,
            "bottom_students": bottom_students,
        })
    except Exception as e:
        logger.exception("get_class_conduct_overview failed")
        return ToolResult(success=False, error=str(e))
