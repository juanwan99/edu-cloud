"""Knowledge tools — Pydantic AI native (migrated from ai/tools/knowledge.py)."""
from __future__ import annotations

import json

from pydantic_ai import RunContext

from edu_cloud.ai.engine.agent_deps import AgentDeps
from edu_cloud.ai.engine.tool_wrapper import edu_tool

_KNOWLEDGE_ROLES = frozenset({
    "platform_admin", "district_admin", "school_admin", "principal",
    "academic_director", "grade_leader",
    "homeroom_teacher", "subject_teacher",
})


@edu_tool(name="search_curriculum", module_code="research", domain="knowledge", allowed_roles=_KNOWLEDGE_ROLES, sensitivity="public")
async def search_curriculum(ctx: RunContext[AgentDeps], keyword: str) -> str:
    """Search curriculum standards by keyword."""
    from edu_cloud.ai.knowledge.store import knowledge_store
    results = knowledge_store.search_curriculum(keyword)
    return json.dumps({"results": results}, ensure_ascii=False, default=str)


@edu_tool(name="search_textbook", module_code="research", domain="knowledge", allowed_roles=_KNOWLEDGE_ROLES, sensitivity="public")
async def search_textbook(ctx: RunContext[AgentDeps], keyword: str) -> str:
    """Search textbook knowledge points by keyword."""
    from edu_cloud.ai.knowledge.store import knowledge_store
    results = knowledge_store.search_knowledge(keyword)
    return json.dumps({"results": results}, ensure_ascii=False, default=str)


@edu_tool(name="get_concept_info", module_code="research", domain="knowledge", allowed_roles=_KNOWLEDGE_ROLES, sensitivity="public")
async def get_concept_info(ctx: RunContext[AgentDeps], concept_name: str) -> str:
    """Get detailed information about a knowledge concept."""
    from edu_cloud.ai.knowledge.store import knowledge_store
    concept = knowledge_store.get_concept(concept_name)
    if not concept:
        return json.dumps({"error": f"未找到概念: {concept_name}"})
    return json.dumps(concept, ensure_ascii=False, default=str)


@edu_tool(name="search_gaokao", module_code="research", domain="knowledge", allowed_roles=_KNOWLEDGE_ROLES, sensitivity="public")
async def search_gaokao(ctx: RunContext[AgentDeps], year: str | None = None, region: str | None = None) -> str:
    """Search gaokao (college entrance exam) questions by year and region."""
    from edu_cloud.ai.knowledge.store import knowledge_store
    results = knowledge_store.search_gaokao(year=year, region=region)
    return json.dumps({"results": results}, ensure_ascii=False, default=str)


ALL_TOOLS = [search_curriculum, search_textbook, get_concept_info, search_gaokao]
