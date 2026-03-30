"""L4 执行动作工具 — generate_report + generate_comment，注册到全局 registry。"""

from sqlalchemy.ext.asyncio import AsyncSession

from edu_cloud.ai.registry import tools
from edu_cloud.services.studio_service import StudioService
from edu_cloud.templates.document_templates import TEMPLATES


@tools.register(
    name="generate_report",
    description="根据模板和上下文生成报告草稿。返回文档 ID，教师可在 Studio 中编辑。",
    parameters={
        "type": "object",
        "properties": {
            "template": {
                "type": "string",
                "description": "模板 key：class_report / subject_analysis / parent_notification",
            },
            "context": {
                "type": "object",
                "description": "上下文参数，如 exam_id, class_id",
            },
        },
        "required": ["template", "context"],
    },
    category="L4_action",
    domain="action",
    allowed_roles=["platform_admin", "academic_director", "subject_teacher", "homeroom_teacher"],
    risk_level="med",
)
async def generate_report(
    template: str,
    context: dict,
    _db: AsyncSession = None,
    _school_id: str = None,
    _user_id: str = None,
    _class_ids: list = None,
) -> dict:
    if template not in TEMPLATES:
        return {"error": f"未知模板: {template}"}

    tmpl = TEMPLATES[template]

    missing = [k for k in tmpl.get("required_context", []) if k not in context]
    if missing:
        return {"error": f"缺少必需上下文: {', '.join(missing)}"}

    svc = StudioService(_db)

    # Gather data from L1 analytics tools
    from edu_cloud.ai.tools.analytics import get_exam_scores, get_class_stats

    data_summary: dict = {}
    try:
        if "exam_id" in context:
            scores = await get_exam_scores(
                exam_id=context["exam_id"],
                _db=_db,
                _school_id=_school_id,
                _class_ids=_class_ids,
            )
            data_summary["scores"] = scores
        if "class_id" in context and "exam_id" in context:
            stats = await get_class_stats(
                exam_id=context["exam_id"],
                class_id=context["class_id"],
                _db=_db,
                _school_id=_school_id,
                _class_ids=_class_ids,
            )
            data_summary["stats"] = stats
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

    doc = await svc.create_document(
        type="report" if "notification" not in template else "notification",
        title=f"{tmpl['name']}",
        content_json=content,
        school_id=_school_id,
        created_by=_user_id,
        source_context=context,
    )
    await _db.commit()

    return {
        "document_id": doc.id,
        "title": doc.title,
        "status": doc.status,
        "type": doc.type,
        "sections": list(content.keys()),
        "requires_approval": tmpl.get("requires_approval", False),
        "message": f"已创建{tmpl['name']}草稿，请在右栏 Studio 中查看和编辑。",
    }


def _build_section_content(section_key: str, data_summary: dict) -> str:
    """Build placeholder content for a section based on available data."""
    scores = data_summary.get("scores", {})
    stats = data_summary.get("stats", {})

    if section_key == "overview" and stats:
        avg = stats.get("avg", "N/A")
        count = stats.get("count", "N/A")
        return f"全班 {count} 人参加考试，平均分 {avg}。"

    if section_key == "subject_analysis" and scores:
        return (
            f"成绩数据已加载（共 {len(scores.get('students', []))} 条记录），"
            "待教师审阅和 AI 细化。"
        )

    if section_key == "student_tiers" and stats:
        return f"基于考试数据的分层分析，待教师审阅。"

    return ""


@tools.register(
    name="generate_comment",
    description="为指定学生生成评语草稿。",
    parameters={
        "type": "object",
        "properties": {
            "student_number": {
                "type": "string",
                "description": "学生学号",
            },
        },
        "required": ["student_number"],
    },
    category="L4_action",
    domain="action",
    allowed_roles=["platform_admin", "academic_director", "subject_teacher", "homeroom_teacher"],
    risk_level="med",
)
async def generate_comment(
    student_number: str,
    _db: AsyncSession = None,
    _school_id: str = None,
    _user_id: str = None,
    _class_ids: list = None,
) -> dict:
    from edu_cloud.models.student import Student
    from sqlalchemy import select

    q = select(Student).where(
        Student.student_number == student_number,
        Student.school_id == _school_id,
    )
    # Scope check: restrict to classes the user has access to.
    # _class_ids=None means unrestricted (platform_admin), [] means no access.
    if _class_ids is not None:
        if not _class_ids:
            return {"error": f"学生 {student_number} 不存在"}
        q = q.where(Student.class_id.in_(_class_ids))

    student = (await _db.execute(q)).scalar_one_or_none()
    if not student:
        return {"error": f"学生 {student_number} 不存在"}

    svc = StudioService(_db)
    doc = await svc.create_document(
        type="comment",
        title=f"{student.name} 评语",
        content_json={
            "student_name": student.name,
            "student_number": student.student_number,
            "academic": {"title": "学业表现", "content": ""},
            "growth": {"title": "成长建议", "content": ""},
        },
        school_id=_school_id,
        created_by=_user_id,
        source_context={"student_id": student.id},
    )
    await _db.commit()

    return {
        "document_id": doc.id,
        "type": "comment",
        "title": doc.title,
        "status": "draft",
        "message": f"已为{student.name}创建评语草稿。",
    }
