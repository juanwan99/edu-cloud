"""知识点 DB 查询工具（2 个）。L3_knowledge_db 类别。

基于 modules/knowledge 的关系型数据库查询（与 knowledge.py 的内存索引互补）。
"""
from edu_cloud.ai.registry import tools


@tools.register(
    name="get_knowledge_tree",
    description="获取某学科的知识点树。返回指定层级的知识点列表。不传 parent_id 返回顶层节点。",
    category="L3_knowledge_db",
    parameters={
        "type": "object",
        "properties": {
            "course_code": {"type": "string", "description": "学科代码，如 SX(数学)、YW(语文)、YY(英语)"},
            "parent_id": {"type": "string", "description": "父知识点 ID，不传则返回顶层"},
        },
        "required": ["course_code"],
    },
)
async def get_knowledge_tree(course_code: str, parent_id: str | None = None, _db=None, _school_id=None, **_):
    from edu_cloud.modules.knowledge.service import list_knowledge_points
    kps = await list_knowledge_points(
        _db, course_code=course_code, parent_id=parent_id,
        school_id=_school_id,
    )
    return {
        "knowledge_points": [
            {"id": kp.id, "code": kp.code, "name": kp.name, "level": kp.level, "grade_hint": kp.grade_hint}
            for kp in kps
        ]
    }


@tools.register(
    name="get_question_knowledge_points",
    description="获取某道题目关联的知识点列表。",
    category="L3_knowledge_db",
    parameters={
        "type": "object",
        "properties": {
            "question_id": {"type": "string", "description": "题目 ID"},
        },
        "required": ["question_id"],
    },
)
async def get_question_knowledge_points(question_id: str, _db=None, **_):
    from edu_cloud.modules.knowledge.service import get_question_knowledge_points as svc_get
    kps = await svc_get(_db, question_id=question_id)
    return {
        "knowledge_points": [
            {"id": kp.id, "code": kp.code, "name": kp.name, "level": kp.level}
            for kp in kps
        ]
    }
