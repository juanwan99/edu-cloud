"""Agent tools for reading/writing cross-session memory."""
import logging

from edu_cloud.ai.memory_store import MemoryStore
from edu_cloud.ai.registry import tools
from edu_cloud.ai.tool_context import ToolContext, ToolResult

logger = logging.getLogger(__name__)

_store = MemoryStore()


@tools.register(
    name="memory_read",
    description=(
        "查询跨会话记忆：学生画像、教师偏好、历史会话摘要。"
        "参数: entity_type (student/teacher/class/session_episode), "
        "entity_ids (可选，不传则返回全部)。"
    ),
    parameters={
        "type": "object",
        "properties": {
            "entity_type": {
                "type": "string",
                "enum": ["student", "teacher", "class", "session_episode"],
                "description": "实体类型",
            },
            "entity_ids": {
                "type": "array",
                "items": {"type": "string"},
                "description": "实体 ID 列表（可选，不传返回全部）",
            },
        },
        "required": ["entity_type"],
    },
    domain="system",
    sensitivity="school",
    allowed_roles=[
        "subject_teacher", "homeroom_teacher", "grade_leader",
        "academic_director", "principal",
    ],
    requires_capabilities=[("system", "read")],
    is_read_only=True,
)
async def memory_read(input_data: dict, ctx: ToolContext) -> ToolResult:
    entity_type = input_data["entity_type"]
    entity_ids = input_data.get("entity_ids")

    visible_student_ids = None
    if entity_type == "student" and ctx.data_scope:
        visible_student_ids = ctx.data_scope.visible_student_ids

    entities = await _store.get_entities(
        ctx.db, ctx.school_id, entity_type,
        entity_ids=entity_ids,
        visible_student_ids=visible_student_ids,
    )

    data = [
        {"entity_id": e.entity_id, "facts": e.facts}
        for e in entities
    ]
    return ToolResult(success=True, data=data)


@tools.register(
    name="memory_write",
    description=(
        "写入跨会话记忆：保存学生学情发现、教师偏好等。"
        "新 facts 与已有 facts 合并（不覆盖）。"
        "参数: entity_type, entity_id, facts (dict)。"
    ),
    parameters={
        "type": "object",
        "properties": {
            "entity_type": {
                "type": "string",
                "enum": ["student", "teacher", "class"],
                "description": "实体类型",
            },
            "entity_id": {
                "type": "string",
                "description": "实体 ID",
            },
            "facts": {
                "type": "object",
                "description": "要保存的事实键值对",
            },
        },
        "required": ["entity_type", "entity_id", "facts"],
    },
    domain="system",
    sensitivity="school",
    allowed_roles=[
        "subject_teacher", "homeroom_teacher", "grade_leader",
        "academic_director", "principal",
    ],
    requires_capabilities=[("system", "write")],
    is_read_only=False,
)
async def memory_write(input_data: dict, ctx: ToolContext) -> ToolResult:
    entity_type = input_data["entity_type"]
    entity_id = input_data["entity_id"]
    facts = input_data.get("facts", {})

    if not facts:
        return ToolResult(success=False, error="facts 不能为空")

    result = await _store.upsert_entity(
        ctx.db,
        school_id=ctx.school_id,
        entity_type=entity_type,
        entity_id=entity_id,
        facts=facts,
    )
    return ToolResult(
        success=True,
        data={"entity_id": result.entity_id, "facts": result.facts},
    )
