"""L3 知识查询工具 — 课标/教材/概念/高考，注册到全局 registry。"""

from edu_cloud.ai.registry import tools
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
)
async def search_curriculum(keyword: str) -> dict:
    results = knowledge_store.search_curriculum(keyword)
    return {"keyword": keyword, "results": results, "count": len(results)}


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
)
async def search_textbook(keyword: str) -> dict:
    blocks = knowledge_store.search_knowledge(keyword)
    return {"keyword": keyword, "blocks": blocks, "count": len(blocks)}


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
)
async def get_concept_info(concept_name: str) -> dict:
    concept = knowledge_store.get_concept(concept_name)
    if not concept:
        return {"error": f"未找到概念: {concept_name}"}
    return {"concept": concept}


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
)
async def search_gaokao(year: int | None = None, region: str | None = None) -> dict:
    exams = knowledge_store.search_gaokao(year=year, region=region)
    return {"exams": exams, "count": len(exams)}
