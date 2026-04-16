"""L3 知识查询工具 — 课标/教材/概念/高考，注册到全局 registry。"""

from edu_cloud.ai.registry import tools
from edu_cloud.ai.tool_context import ToolContext, ToolResult
from edu_cloud.knowledge.store import knowledge_store

@tools.register(
    name="search_curriculum",
    description="搜索课程标准（课标）内容。输入关键词，返回匹配的学业要求和核心素养描述。",
    parameters={
        "type": "object",
        "properties": {
            "keyword": {"type": "string", "description": "搜索关键词，如'基因表达'、'细胞分裂'"},
        },
        "required": ["keyword"],
    },
    category="L3_knowledge",
    domain="knowledge",
    allowed_roles=["platform_admin", "district_admin", "principal", "academic_director", "grade_leader", "homeroom_teacher", "subject_teacher"],
    risk_level="low",
    is_read_only=True,
    sensitivity="public",
)
async def search_curriculum(input: dict, ctx: ToolContext) -> ToolResult:
    keyword = input.get("keyword", "")
    try:
        results = knowledge_store.search_curriculum(keyword)
        return ToolResult(success=True, data={"keyword": keyword, "results": results, "count": len(results)})
    except Exception as e:
        return ToolResult(success=False, error=str(e))


@tools.register(
    name="search_textbook",
    description="搜索教材内容（知识块）。输入关键词，返回匹配的教材段落和知识分类。",
    parameters={
        "type": "object",
        "properties": {
            "keyword": {"type": "string", "description": "搜索关键词"},
        },
        "required": ["keyword"],
    },
    category="L3_knowledge",
    domain="knowledge",
    allowed_roles=["platform_admin", "district_admin", "principal", "academic_director", "grade_leader", "homeroom_teacher", "subject_teacher"],
    risk_level="low",
    is_read_only=True,
    sensitivity="public",
)
async def search_textbook(input: dict, ctx: ToolContext) -> ToolResult:
    keyword = input.get("keyword", "")
    try:
        blocks = knowledge_store.search_knowledge(keyword)
        return ToolResult(success=True, data={"keyword": keyword, "blocks": blocks, "count": len(blocks)})
    except Exception as e:
        return ToolResult(success=False, error=str(e))


@tools.register(
    name="get_concept_info",
    description="获取某个生物学概念的详细信息，包括定义、关联知识块、所属模块。",
    parameters={
        "type": "object",
        "properties": {
            "concept_name": {"type": "string", "description": "概念名称，如'细胞学说'、'基因表达'"},
        },
        "required": ["concept_name"],
    },
    category="L3_knowledge",
    domain="knowledge",
    allowed_roles=["platform_admin", "district_admin", "principal", "academic_director", "grade_leader", "homeroom_teacher", "subject_teacher"],
    risk_level="low",
    is_read_only=True,
    sensitivity="public",
)
async def get_concept_info(input: dict, ctx: ToolContext) -> ToolResult:
    concept_name = input.get("concept_name", "")
    try:
        concept = knowledge_store.get_concept(concept_name)
        if not concept:
            return ToolResult(success=False, error=f"未找到概念: {concept_name}")
        return ToolResult(success=True, data={"concept": concept})
    except Exception as e:
        return ToolResult(success=False, error=str(e))


@tools.register(
    name="search_gaokao",
    description="搜索高考真题。可按年份或地区筛选，返回考试列表。",
    parameters={
        "type": "object",
        "properties": {
            "year": {"type": "integer", "description": "年份，如 2024"},
            "region": {"type": "string", "description": "地区，如'北京'、'江苏'"},
        },
    },
    category="L3_knowledge",
    domain="knowledge",
    allowed_roles=["platform_admin", "district_admin", "principal", "academic_director", "grade_leader", "homeroom_teacher", "subject_teacher"],
    risk_level="low",
    is_read_only=True,
    sensitivity="public",
)
async def search_gaokao(input: dict, ctx: ToolContext) -> ToolResult:
    year = input.get("year")
    region = input.get("region")
    try:
        exams = knowledge_store.search_gaokao(year=year, region=region)
        return ToolResult(success=True, data={"exams": exams, "count": len(exams)})
    except Exception as e:
        return ToolResult(success=False, error=str(e))
