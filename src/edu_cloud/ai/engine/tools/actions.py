"""Action tools — Pydantic AI native (migrated from ai/tools/actions.py).

generate_report: creates a Studio document draft with data gathered inline.
generate_comment: creates a student comment draft.
"""
from __future__ import annotations

import json

from pydantic_ai import RunContext
from sqlalchemy import select, func

from edu_cloud.ai.engine.agent_deps import AgentDeps
from edu_cloud.ai.engine.tool_wrapper import edu_tool

_ACTION_ROLES = frozenset({
    "platform_admin", "academic_director",
    "homeroom_teacher", "subject_teacher",
})


def _build_section_content(section_key: str, data_summary: dict) -> str:
    scores = data_summary.get("scores", {})
    stats = data_summary.get("stats", {})

    if section_key == "overview" and stats:
        avg = stats.get("avg", "N/A")
        count = stats.get("count", "N/A")
        return f"全班 {count} 人参加考试，平均分 {avg}。"

    if section_key == "subject_analysis" and scores:
        return (
            f"成绩数据已加载（共 {scores.get('student_count', 0)} 条记录），"
            "待教师审阅和 AI 细化。"
        )

    if section_key == "student_tiers" and stats:
        return "基于考试数据的分层分析，待教师审阅。"

    return ""


@edu_tool(
    name="generate_report", module_code="exam", domain="action",
    allowed_roles=_ACTION_ROLES, risk_level="medium", is_read_only=False, sensitivity="school",
)
async def generate_report(ctx: RunContext[AgentDeps], template: str, context: dict | None = None) -> str:
    """Generate a report draft from a template. Returns document ID for Studio editing."""
    from edu_cloud.templates.document_templates import TEMPLATES
    from edu_cloud.services.studio_service import StudioService

    context = context or {}
    if template not in TEMPLATES:
        return json.dumps({"error": f"未知模板: {template}"})

    tmpl = TEMPLATES[template]
    missing = [k for k in tmpl.get("required_context", []) if k not in context]
    if missing:
        return json.dumps({"error": f"缺少必需上下文: {', '.join(missing)}"})

    scope = ctx.deps.data_scope

    data_summary: dict = {}
    async with ctx.deps.get_db() as db:
        try:
            from edu_cloud.modules.exam.models import ExamResult
            from edu_cloud.modules.student.models import Student

            if "exam_id" in context:
                stmt = (
                    select(ExamResult, Student)
                    .join(Student, ExamResult.student_id == Student.id)
                    .where(ExamResult.exam_id == context["exam_id"])
                    .where(ExamResult.school_id == scope.school_id)
                )
                if scope.visible_class_ids is not None:
                    stmt = stmt.where(Student.class_id.in_(scope.visible_class_ids))
                rows = (await db.execute(stmt)).all()
                data_summary["scores"] = {"student_count": len(rows)}

            if "class_id" in context and "exam_id" in context:
                class_id = context["class_id"]
                if scope.visible_class_ids is not None and class_id not in scope.visible_class_ids:
                    pass
                else:
                    stmt = (
                        select(func.count(), func.avg(ExamResult.total_score))
                        .join(Student, ExamResult.student_id == Student.id)
                        .where(ExamResult.exam_id == context["exam_id"])
                        .where(Student.class_id == class_id)
                        .where(ExamResult.school_id == scope.school_id)
                    )
                    row = (await db.execute(stmt)).one()
                    data_summary["stats"] = {
                        "count": row[0],
                        "avg": round(float(row[1]), 1) if row[1] else "N/A",
                    }
        except Exception:
            pass

        content = {}
        for section in tmpl["sections"]:
            section_content = _build_section_content(section["key"], data_summary)
            content[section["key"]] = {
                "title": section["title"],
                "content": section_content,
                "prompt": section["prompt"],
            }

        svc = StudioService(db)
        doc = await svc.create_document(
            type="report" if "notification" not in template else "notification",
            title=tmpl["name"],
            content_json=content,
            school_id=scope.school_id,
            created_by=ctx.deps.user_id,
            source_context=context,
        )
        await db.commit()

    return json.dumps({
        "document_id": doc.id,
        "title": doc.title,
        "status": doc.status,
        "type": doc.type,
        "sections": list(content.keys()),
        "message": f"已创建{tmpl['name']}草稿，请在右栏 Studio 中查看和编辑。",
    }, ensure_ascii=False, default=str)


@edu_tool(
    name="generate_comment", module_code="exam", domain="action",
    allowed_roles=_ACTION_ROLES, risk_level="medium", is_read_only=False, sensitivity="student",
)
async def generate_comment(ctx: RunContext[AgentDeps], student_number: str) -> str:
    """Generate a student comment draft. Returns document ID for Studio editing."""
    from edu_cloud.modules.student.models import Student
    from edu_cloud.services.studio_service import StudioService

    scope = ctx.deps.data_scope

    async with ctx.deps.get_db() as db:
        q = select(Student).where(
            Student.student_number == student_number,
            Student.school_id == scope.school_id,
        )
        if scope.visible_class_ids is not None:
            if not scope.visible_class_ids:
                return json.dumps({"error": f"学生 {student_number} 不存在"})
            q = q.where(Student.class_id.in_(scope.visible_class_ids))

        student = (await db.execute(q)).scalar_one_or_none()
        if not student:
            return json.dumps({"error": f"学生 {student_number} 不存在"})

        svc = StudioService(db)
        doc = await svc.create_document(
            type="comment",
            title=f"{student.name} 评语",
            content_json={
                "student_name": student.name,
                "student_number": student.student_number,
                "academic": {"title": "学业表现", "content": ""},
                "growth": {"title": "成长建议", "content": ""},
            },
            school_id=scope.school_id,
            created_by=ctx.deps.user_id,
            source_context={"student_id": student.id},
        )
        await db.commit()

    return json.dumps({
        "document_id": doc.id,
        "type": "comment",
        "title": doc.title,
        "status": "draft",
        "message": f"已为{student.name}创建评语草稿。",
    }, ensure_ascii=False, default=str)


_CONDUCT_ROLES = frozenset({
    "platform_admin", "academic_director", "grade_leader",
    "homeroom_teacher", "subject_teacher",
})


@edu_tool(
    name="draft_parent_notification", module_code="conduct", domain="action",
    allowed_roles=_CONDUCT_ROLES, risk_level="high", is_read_only=False, sensitivity="student",
)
async def draft_parent_notification(
    ctx: RunContext[AgentDeps],
    student_ids: list[str],
    subject: str,
    template: str = "score_alert",
) -> str:
    """为指定学生家长生成通知草稿（不发送，存入 Studio 待审批）。"""
    from edu_cloud.modules.student.models import Student
    from edu_cloud.modules.studio.service import StudioService

    if not student_ids:
        return json.dumps({"error": "student_ids 不能为空"})
    if len(student_ids) > 50:
        return json.dumps({"error": "单次最多 50 名学生"})

    scope = ctx.deps.data_scope
    async with ctx.deps.get_db() as db:
        stmt = select(Student).where(
            Student.id.in_(student_ids),
            Student.school_id == scope.school_id,
        )
        if scope.visible_class_ids is not None:
            stmt = stmt.where(Student.class_id.in_(scope.visible_class_ids))
        students = list((await db.execute(stmt)).scalars().all())

        if not students:
            return json.dumps({"error": "未找到符合条件的学生"})

        student_names = [s.name for s in students]
        svc = StudioService(db)
        doc = await svc.create_document(
            type="notification",
            title=f"{subject} 成绩通知（{len(students)} 名学生家长）",
            content_json={
                "template": template,
                "subject": subject,
                "students": [{"id": s.id, "name": s.name, "number": s.student_number} for s in students],
                "body": "",
            },
            school_id=scope.school_id,
            created_by=ctx.deps.user_id,
            source_context={"student_ids": student_ids, "template": template},
        )
        await db.commit()

    return json.dumps({
        "document_id": doc.id,
        "type": "notification",
        "title": doc.title,
        "status": "draft",
        "student_count": len(students),
        "students": student_names[:10],
        "message": f"已为 {len(students)} 名学生家长创建{subject}成绩通知草稿，请在 Studio 中审批后发送。",
    }, ensure_ascii=False, default=str)


ALL_TOOLS = [generate_report, generate_comment, draft_parent_notification]
