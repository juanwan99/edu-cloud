"""学生学情画像域工具 — 聚合趋势+知识掌握+错误模式。"""
from sqlalchemy import select

from edu_cloud.ai.registry import tools
from edu_cloud.ai.tool_context import ToolContext, ToolResult


@tools.register(
    name="get_student_learning_profile",
    description="获取学生学情画像：成绩趋势、知识点掌握、错误模式。家长和教师均可使用。",
    parameters={
        "type": "object",
        "properties": {
            "student_id": {"type": "string", "description": "学生 ID"},
            "subject_code": {"type": "string", "description": "科目代码（可选）"},
        },
        "required": ["student_id"],
    },
    category="profile",
    domain="student_profile",
    allowed_roles=[
        "platform_admin", "district_admin", "principal",
        "academic_director", "grade_leader", "homeroom_teacher",
        "subject_teacher", "parent",
    ],
    risk_level="low",
    is_read_only=True,
    sensitivity="student",
)
async def get_student_learning_profile(input: dict, ctx: ToolContext) -> ToolResult:
    student_id = input["student_id"]
    subject_code = input.get("subject_code")

    # Enforce DataScope student visibility (parent can only see linked children)
    if ctx.data_scope is not None and ctx.data_scope.visible_student_ids is not None:
        if student_id not in ctx.data_scope.visible_student_ids:
            return ToolResult(success=False, error="无权访问该学生信息")

    # 1. Get recent exam snapshots (last 10)
    from edu_cloud.modules.profile.models import StudentExamSnapshot

    query = select(StudentExamSnapshot).where(
        StudentExamSnapshot.student_id == student_id,
        StudentExamSnapshot.school_id == ctx.school_id,
    )
    if subject_code:
        query = query.where(StudentExamSnapshot.subject_code == subject_code)
    query = query.order_by(StudentExamSnapshot.created_at.desc()).limit(10)
    snapshots = (await ctx.db.execute(query)).scalars().all()

    if not snapshots:
        return ToolResult(
            success=True,
            data={"status": "no_data", "message": "暂无该学生的考试数据"},
        )

    # 2. Build trend
    # F1: Parents should not see class_rank (ToolContext lacks can_see_rankings,
    # so we conservatively strip rank for all parents).
    include_rank = ctx.role != "parent"
    trend = []
    for s in snapshots:
        entry: dict = {
            "exam_id": s.exam_id,
            "subject": s.subject_code,
            "score_rate": s.score_rate,
        }
        if include_rank:
            entry["rank"] = s.class_rank
        trend.append(entry)

    # 3. Get knowledge mastery (weak points)
    from edu_cloud.modules.profile.models import StudentKnowledgeMastery

    mastery = (
        await ctx.db.execute(
            select(StudentKnowledgeMastery)
            .where(StudentKnowledgeMastery.student_id == student_id)
            .where(StudentKnowledgeMastery.school_id == ctx.school_id)
            .order_by(StudentKnowledgeMastery.mastery_level.asc())
            .limit(20)
        )
    ).scalars().all()

    weak_points = [
        {
            "kp": m.concept_id,
            "mastery": m.mastery_level,
            "attempts": m.attempt_count,
        }
        for m in mastery
        if m.mastery_level < 0.6
    ]

    return ToolResult(
        success=True,
        data={
            "trend": trend,
            "weak_points": weak_points,
            "latest_score_rate": snapshots[0].score_rate if snapshots else None,
            "exam_count": len(snapshots),
        },
    )
