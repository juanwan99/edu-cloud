"""知识树编辑工具（教师通过 Agent 对话修改知识图谱）。"""

from edu_cloud.ai.registry import tools
from edu_cloud.ai.tool_context import ToolContext, ToolResult


@tools.register(
    name="edit_knowledge_graph",
    description=(
        "编辑知识图谱结构。支持操作：add_node（增加概念）、remove_node（删除概念，级联删边）、"
        "update_node（改名/改描述）、add_edge（加关系）、remove_edge（删关系）、"
        "update_edge（改关系强度）。"
        "概念 ID 格式: BIO_SR_CP_M{N}_{SNAKE_CASE_NAME}。"
        "关系类型: prerequisite_hard（硬前置）/ bridge_to（桥接）/ contrast（对比）。"
    ),
    category="L1_knowledge",
    module_code="research",
    domain="knowledge",
    allowed_roles=["platform_admin", "district_admin", "principal", "subject_teacher", "homeroom_teacher"],
    risk_level="medium",
    is_read_only=False,
    sensitivity="school",
    parameters={
        "operations": {
            "type": "array",
            "description": "批量编辑操作列表",
            "items": {
                "type": "object",
                "properties": {
                    "op": {
                        "type": "string",
                        "enum": ["add_node", "remove_node", "update_node",
                                 "add_edge", "remove_edge", "update_edge"],
                    },
                    "id": {"type": "string", "description": "节点 ID（node 操作用）"},
                    "name": {"type": "string", "description": "节点名称（add_node 用）"},
                    "level": {"type": "string", "description": "知识层级 L0/L1/L2"},
                    "module": {"type": "string", "description": "模块 M1-M5"},
                    "description": {"type": "string"},
                    "source": {"type": "string", "description": "边的源节点 ID"},
                    "target": {"type": "string", "description": "边的目标节点 ID"},
                    "type": {"type": "string", "description": "关系类型"},
                    "strength": {"type": "number", "description": "关系强度 0-1"},
                    "fields": {"type": "object", "description": "update 操作的字段"},
                },
                "required": ["op"],
            },
        },
    },
)
async def edit_knowledge_graph(input: dict, ctx: ToolContext) -> ToolResult:
    try:
        from edu_cloud.modules.knowledge_tree.service import apply_edits
        operations = input.get("operations", [])
        if not operations:
            return ToolResult(success=False, error="operations 不能为空")
        applied = await apply_edits(ctx.db, operations)
        return ToolResult(success=True, data={
            "message": f"成功执行 {applied} 个操作",
            "applied": applied,
        })
    except Exception as e:
        return ToolResult(success=False, error=str(e))
