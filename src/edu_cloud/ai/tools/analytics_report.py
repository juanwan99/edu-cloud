"""分析报告 AI 工具（3 个）。L2_analytics 类别。"""
from edu_cloud.ai.registry import tools
from edu_cloud.ai.tool_context import ToolContext, ToolResult


@tools.register(
    name="get_score_segments",
    description="获取本校分数段配置，以及某次考试按分数段的学生分布。",
    category="L2_analytics",
    module_code="exam",
    domain="analytics",
    allowed_roles=["platform_admin", "academic_director", "grade_leader", "homeroom_teacher"],
    risk_level="low",
    is_read_only=True,
    sensitivity="school",
    parameters={
        "type": "object",
        "properties": {
            "exam_id": {"type": "string", "description": "考试 ID"},
            "subject_code": {"type": "string", "description": "可选，科目代码（用科目覆盖配置）"},
        },
        "required": ["exam_id"],
    },
)
async def get_score_segments(input: dict, ctx: ToolContext) -> ToolResult:
    exam_id = input.get("exam_id", "")
    subject_code = input.get("subject_code")
    try:
        from edu_cloud.modules.analytics.segment_service import get_segment_config
        from edu_cloud.modules.analytics.service import exam_distribution

        boundaries, labels = await get_segment_config(ctx.db, ctx.school_id, subject_code)
        effective_subject_codes = ctx.subject_codes
        if subject_code:
            if effective_subject_codes:
                effective_subject_codes = [c for c in effective_subject_codes if c == subject_code]
            else:
                effective_subject_codes = [subject_code]
        dist = await exam_distribution(
            ctx.db, exam_id=exam_id, school_id=ctx.school_id,
            visible_subject_codes=effective_subject_codes,
            visible_class_ids=ctx.class_ids,
        )
        return ToolResult(success=True, data={
            "config": {"boundaries": boundaries, "labels": labels},
            "distribution": dist,
        })
    except Exception as e:
        return ToolResult(success=False, error=str(e))


@tools.register(
    name="compare_exams",
    description="跨考试对比趋势。支持年级/班级/学生三种维度。返回多次考试的趋势数据点。",
    category="L2_analytics",
    module_code="exam",
    domain="analytics",
    allowed_roles=["platform_admin", "academic_director", "grade_leader", "homeroom_teacher"],
    risk_level="low",
    is_read_only=True,
    sensitivity="school",
    parameters={
        "type": "object",
        "properties": {
            "exam_ids": {"type": "array", "items": {"type": "string"}, "description": "考试 ID 列表（2+）"},
            "target_type": {"type": "string", "enum": ["grade", "class", "student"], "description": "对比维度"},
            "target_id": {"type": "string", "description": "class 维度传 class_id，student 维度传 student_id"},
            "subject_code": {"type": "string", "description": "可选，按科目过滤"},
        },
        "required": ["exam_ids", "target_type"],
    },
)
async def compare_exams(input: dict, ctx: ToolContext) -> ToolResult:
    exam_ids = input.get("exam_ids", [])
    target_type = input.get("target_type", "grade")
    target_id = input.get("target_id")
    subject_code = input.get("subject_code")

    if not exam_ids:
        return ToolResult(success=False, error="需要提供 exam_ids")

    try:
        from edu_cloud.modules.analytics.report_service import (
            get_grade_trend, get_class_trend, get_student_trend,
        )

        if target_type == "grade":
            data = await get_grade_trend(
                ctx.db, ctx.school_id, exam_ids, subject_code,
                visible_subject_codes=ctx.subject_codes,
            )
        elif target_type == "class":
            if not target_id:
                return ToolResult(success=False, error="class 维度需要提供 target_id (class_id)")
            if ctx.class_ids is not None and target_id not in ctx.class_ids:
                return ToolResult(success=False, error="无权访问该班级")
            data = await get_class_trend(
                ctx.db, ctx.school_id, exam_ids, target_id, subject_code,
                visible_subject_codes=ctx.subject_codes,
            )
        elif target_type == "student":
            if not target_id:
                return ToolResult(success=False, error="student 维度需要提供 target_id (student_id)")
            # 学生可见性校验
            if ctx.class_ids is not None:
                from sqlalchemy import select as sa_select
                from edu_cloud.modules.student.models import Student
                stu_result = await ctx.db.execute(
                    sa_select(Student.class_id).where(
                        Student.id == target_id, Student.school_id == ctx.school_id
                    )
                )
                stu_row = stu_result.first()
                if not stu_row or stu_row.class_id not in ctx.class_ids:
                    return ToolResult(success=False, error="无权查看该学生数据")
            data = await get_student_trend(
                ctx.db, ctx.school_id, exam_ids, target_id, subject_code,
                visible_subject_codes=ctx.subject_codes,
            )
        else:
            return ToolResult(success=False, error=f"不支持的 target_type: {target_type}")

        return ToolResult(success=True, data=data)
    except Exception as e:
        return ToolResult(success=False, error=str(e))


@tools.register(
    name="generate_analysis_report",
    description="生成考试分析报告文档（PDF）。创建 Studio 文档，可通过文档中心下载。",
    category="L2_analytics",
    module_code="exam",
    domain="analytics",
    allowed_roles=["platform_admin", "academic_director", "grade_leader"],
    risk_level="medium",
    is_read_only=False,
    sensitivity="school",
    parameters={
        "type": "object",
        "properties": {
            "exam_ids": {"type": "array", "items": {"type": "string"}, "description": "考试 ID 列表"},
            "metrics": {"type": "array", "items": {"type": "string"}, "description": "可选，指标列表"},
            "title": {"type": "string", "description": "可选，报告标题"},
        },
        "required": ["exam_ids"],
    },
)
async def generate_analysis_report(input: dict, ctx: ToolContext) -> ToolResult:
    exam_ids = input.get("exam_ids", [])
    if not exam_ids:
        return ToolResult(success=False, error="需要提供 exam_ids")

    try:
        from edu_cloud.modules.analytics.report_service import build_report
        from edu_cloud.modules.studio.service import StudioService
        from sqlalchemy import select
        from edu_cloud.modules.exam.models import Exam

        report_data = await build_report(
            ctx.db, school_id=ctx.school_id, exam_ids=exam_ids,
            metrics=input.get("metrics"),
            visible_subject_codes=ctx.subject_codes,
            visible_class_ids=ctx.class_ids,
        )

        exam_result = await ctx.db.execute(select(Exam).where(Exam.id == exam_ids[0]))
        exam = exam_result.scalar_one_or_none()
        title = input.get("title") or f"{exam.name if exam else '考试'}分析报告"

        svc = StudioService(ctx.db)
        doc = await svc.create_document(
            type="analysis_report",
            title=title,
            content_json={
                "report_type": "exam_analysis",
                "config": {"exam_ids": exam_ids, "metrics": input.get("metrics")},
                "sections": report_data["metrics"],
            },
            school_id=ctx.school_id,
            created_by=ctx.user_id,
        )
        await svc.transition_status(doc.id, "reviewed", school_id=ctx.school_id)
        await svc.transition_status(doc.id, "executed", school_id=ctx.school_id)
        await ctx.db.commit()

        return ToolResult(success=True, data={
            "document_id": doc.id,
            "title": doc.title,
            "status": "executed",
            "message": f"报告「{title}」已创建并完成状态流转，可在文档中心查看和导出 PDF",
        })
    except Exception as e:
        return ToolResult(success=False, error=str(e))
