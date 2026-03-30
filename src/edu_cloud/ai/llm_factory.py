from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from edu_cloud.ai.llm import LLMChatClient
from edu_cloud.config import settings
from edu_cloud.core.models.llm_slot import LLMSlot


def _tier_condition(tier: str):
    """tier 查询条件：standard 时兼容旧数据（tier=NULL 视为 standard）"""
    if tier == "standard":
        return or_(LLMSlot.tier == "standard", LLMSlot.tier == None)  # noqa: E711
    return LLMSlot.tier == tier


async def create_llm_for_tier(
    tier: str, school_id: str | None, db: AsyncSession
) -> LLMChatClient:
    """按 tier 查询 LLMSlot，返回对应的 LLMChatClient"""
    # 优先：学校级 slot
    slot = None
    if school_id:
        stmt = select(LLMSlot).where(
            LLMSlot.school_id == school_id,
            _tier_condition(tier),
            LLMSlot.is_enabled == True,  # noqa: E712
        ).limit(1)
        result = await db.execute(stmt)
        slot = result.scalar_one_or_none()

    # 其次：平台默认 slot
    if not slot:
        stmt = select(LLMSlot).where(
            LLMSlot.school_id == None,  # noqa: E711
            _tier_condition(tier),
            LLMSlot.is_enabled == True,  # noqa: E712
        ).limit(1)
        result = await db.execute(stmt)
        slot = result.scalar_one_or_none()

    # 兜底：.env 配置
    if not slot:
        return LLMChatClient(
            api_url=settings.LLM_API_URL,
            api_key=settings.LLM_API_KEY,
            model=settings.LLM_MODEL,
        )

    return LLMChatClient(
        api_url=slot.api_url,
        api_key=slot.api_key,
        model=slot.model,
        slot=slot.label or "",
    )
