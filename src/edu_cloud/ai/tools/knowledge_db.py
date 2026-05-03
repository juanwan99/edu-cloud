"""知识点查询工具（统一到 ConceptGraphNode 体系）。"""
from sqlalchemy import select

from edu_cloud.ai.registry import tools
from edu_cloud.ai.tool_context import ToolContext, ToolResult


@tools.register(
    name="get_knowledge_tree",
    description=(
        "获取指定科目的知识点树。返回三层结构：模块→学习单元→概念。"
        "每个节点包含 id（语义化字符串如 BIO_SR_CP_M1_CELL_THEORY）、name、"
        "node_type（module/study_unit/concept）、primary_module、description。"
    ),
    category="L3_knowledge_db",
    module_code="knowledge",
    domain="knowledge",
    parameters={
        "course_code": {"type": "string", "description": "科目代码: SW(生物)/SX(数学)", "default": "SW"},
        "module": {"type": "string", "description": "模块过滤: M1/M2/M3/M4/M5/all", "default": "all"},
    },
)
async def get_knowledge_tree(input: dict, ctx: ToolContext) -> ToolResult:
    from edu_cloud.modules.knowledge_tree.models import ConceptGraphNode, ConceptGraphEdge

    course_code = input.get("course_code", "SW")
    module_filter = input.get("module", "all")

    stmt = select(ConceptGraphNode).where(ConceptGraphNode.course_code == course_code)
    if module_filter != "all":
        stmt = stmt.where(ConceptGraphNode.primary_module == module_filter)

    result = await ctx.db.execute(stmt)
    nodes = result.scalars().all()

    node_ids = [n.id for n in nodes]
    edges = await ctx.db.execute(
        select(ConceptGraphEdge.source_id, ConceptGraphEdge.target_id)
        .where(ConceptGraphEdge.relation_type == "contains",
               ConceptGraphEdge.target_id.in_(node_ids))
    )
    child_to_parent = {row[1]: row[0] for row in edges.all()}

    items = []
    for n in nodes:
        items.append({
            "id": n.id,
            "name": n.name,
            "node_type": n.node_type,
            "primary_module": n.primary_module,
            "description": n.description,
            "parent_id": child_to_parent.get(n.id),
        })

    return ToolResult(success=True, data={"knowledge_points": items, "total": len(items)})


@tools.register(
    name="get_question_knowledge_points",
    description="查询题目关联的知识点。返回概念列表（id + name + module）。",
    category="L3_knowledge_db",
    module_code="knowledge",
    domain="knowledge",
    parameters={
        "question_id": {"type": "string", "description": "题目 ID", "required": True},
    },
)
async def get_question_knowledge_points(input: dict, ctx: ToolContext) -> ToolResult:
    from edu_cloud.modules.knowledge.models import QuestionKnowledgePoint
    from edu_cloud.modules.knowledge_tree.models import ConceptGraphNode

    question_id = input["question_id"]
    result = await ctx.db.execute(
        select(ConceptGraphNode)
        .join(QuestionKnowledgePoint, QuestionKnowledgePoint.concept_id == ConceptGraphNode.id)
        .where(QuestionKnowledgePoint.question_id == question_id)
    )
    nodes = result.scalars().all()
    return ToolResult(success=True, data={
        "knowledge_points": [
            {"id": n.id, "name": n.name, "module": n.primary_module}
            for n in nodes
        ],
    })
