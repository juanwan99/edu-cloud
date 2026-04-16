"""学生画像工具（4 个）。L6_profile 类别。"""
from edu_cloud.ai.registry import tools
from edu_cloud.ai.tool_context import ToolContext, ToolResult


@tools.register(
    name="get_student_trend",
    description="获取某学生的成绩趋势。返回该学生历次考试的分数、排名变化。",
    category="L6_profile",
    domain="profile",
    risk_level="low",
    is_read_only=True,
    sensitivity="student",
    parameters={
        "type": "object",
        "properties": {
            "student_id": {"type": "string", "description": "学生 ID"},
            "subject_code": {"type": "string", "description": "学科代码（可选，不传则返回所有科目）"},
        },
        "required": ["student_id"],
    },
)
async def get_student_trend(input: dict, ctx: ToolContext) -> ToolResult:
    student_id = input.get("student_id", "")
    subject_code = input.get("subject_code")
    try:
        from edu_cloud.modules.profile.service import get_student_trend as svc_trend
        snaps = await svc_trend(
            ctx.db, student_id=student_id, school_id=ctx.school_id, subject_code=subject_code,
        )
        return ToolResult(success=True, data={
            "trend": [
                {
                    "exam_id": s.exam_id, "subject_code": s.subject_code,
                    "total_score": s.total_score, "max_score": s.max_score,
                    "score_rate": s.score_rate, "grade_rank": s.grade_rank,
                    "grade_size": s.grade_size,
                }
                for s in snaps
            ]
        })
    except Exception as e:
        return ToolResult(success=False, error=str(e))


@tools.register(
    name="get_student_knowledge_map",
    description="获取某学生的知识点掌握度。返回各知识点的掌握程度和趋势。",
    category="L6_profile",
    domain="profile",
    risk_level="low",
    is_read_only=True,
    sensitivity="student",
    parameters={
        "type": "object",
        "properties": {
            "student_id": {"type": "string", "description": "学生 ID"},
            "course_code": {"type": "string", "description": "学科代码（如 SX 数学）"},
        },
        "required": ["student_id"],
    },
)
async def get_student_knowledge_map(input: dict, ctx: ToolContext) -> ToolResult:
    student_id = input.get("student_id", "")
    course_code = input.get("course_code")
    try:
        from edu_cloud.modules.profile.service import get_student_knowledge_map as svc_kmap
        masteries = await svc_kmap(
            ctx.db, student_id=student_id, school_id=ctx.school_id, course_code=course_code,
        )
        return ToolResult(success=True, data={
            "knowledge_map": [
                {
                    "knowledge_point_id": m.knowledge_point_id,
                    "mastery_level": m.mastery_level,
                    "trend": m.trend,
                    "attempt_count": m.attempt_count,
                    "recent_scores": m.recent_scores,
                }
                for m in masteries
            ]
        })
    except Exception as e:
        return ToolResult(success=False, error=str(e))


@tools.register(
    name="get_class_knowledge_weakness",
    description="获取某班级的知识薄弱点排名。返回掌握度最低的知识点列表。",
    category="L6_profile",
    domain="profile",
    risk_level="low",
    is_read_only=True,
    sensitivity="student",
    parameters={
        "type": "object",
        "properties": {
            "class_id": {"type": "string", "description": "班级 ID"},
            "course_code": {"type": "string", "description": "学科代码"},
            "top_n": {"type": "integer", "description": "返回最弱的 N 个知识点，默认 5"},
        },
        "required": ["class_id"],
    },
)
async def get_class_knowledge_weakness(input: dict, ctx: ToolContext) -> ToolResult:
    class_id = input.get("class_id", "")
    course_code = input.get("course_code")
    top_n = input.get("top_n", 5)
    try:
        if ctx.class_ids is not None and class_id not in ctx.class_ids:
            return ToolResult(success=False, error="无权查看该班级数据")

        from edu_cloud.modules.student.models import Student
        from sqlalchemy import select
        stu_result = await ctx.db.execute(
            select(Student.id).where(Student.class_id == class_id, Student.school_id == ctx.school_id)
        )
        student_ids = [r[0] for r in stu_result.all()]
        if not student_ids:
            return ToolResult(success=True, data={"weakness": [], "message": "该班级没有学生数据"})

        from edu_cloud.modules.profile.service import get_class_knowledge_weakness as svc_weakness
        weakness = await svc_weakness(
            ctx.db, school_id=ctx.school_id, class_student_ids=student_ids,
            course_code=course_code, top_n=top_n,
        )
        return ToolResult(success=True, data={"weakness": weakness})
    except Exception as e:
        return ToolResult(success=False, error=str(e))


@tools.register(
    name="get_student_error_pattern",
    description="获取某学生的错误模式分析。返回各科目的错误类型分布和统计。",
    category="L6_profile",
    domain="profile",
    risk_level="low",
    is_read_only=True,
    sensitivity="student",
    parameters={
        "type": "object",
        "properties": {
            "student_id": {"type": "string", "description": "学生 ID"},
            "subject_code": {"type": "string", "description": "学科代码（可选）"},
        },
        "required": ["student_id"],
    },
)
async def get_student_error_pattern(input: dict, ctx: ToolContext) -> ToolResult:
    student_id = input.get("student_id", "")
    subject_code = input.get("subject_code")
    try:
        from edu_cloud.modules.profile.service import get_student_error_pattern as svc_pattern
        patterns = await svc_pattern(
            ctx.db, student_id=student_id, school_id=ctx.school_id, subject_code=subject_code,
        )
        return ToolResult(success=True, data={
            "error_patterns": [
                {
                    "subject_code": p.subject_code,
                    "error_distribution": p.error_distribution,
                    "total_errors": p.total_errors,
                    "exam_count": p.exam_count,
                    "careless_rate": p.careless_rate,
                }
                for p in patterns
            ]
        })
    except Exception as e:
        return ToolResult(success=False, error=str(e))
