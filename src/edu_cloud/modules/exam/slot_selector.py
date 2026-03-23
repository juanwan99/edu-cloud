"""LLM 路由层 — 按槽位号 + 学校 ID 获取 LLM 配置。

优先级：学校覆盖 > 平台默认 > .env fallback
"""
import logging
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from edu_cloud.core.models.llm_slot import LLMSlot
from edu_cloud.config import settings
from edu_cloud.services.exceptions import NotFoundError

logger = logging.getLogger(__name__)


async def get_llm_config(
    db: AsyncSession, *, slot: int, school_id: str | None = None,
) -> tuple[str, str, str]:
    """获取 LLM 配置。返回 (api_url, api_key, model)。

    查询顺序：
    1. 学校级覆盖（school_id + slot_number）
    2. 平台默认（school_id=NULL + slot_number）
    3. .env fallback（LLM_API_URL/KEY/MODEL）
    """
    # 1. 学校级覆盖
    if school_id:
        result = await db.execute(
            select(LLMSlot).where(
                LLMSlot.school_id == school_id,
                LLMSlot.slot_number == slot,
                LLMSlot.is_enabled.is_(True),
            )
        )
        config = result.scalar_one_or_none()
        if config:
            logger.debug("llm_router: slot=%d, school=%s → school override (%s)", slot, school_id, config.model)
            return config.api_url, config.api_key, config.model

    # 2. 平台默认（school_id=NULL 不受 UNIQUE 约束，用 first() 防 MultipleResultsFound）
    result = await db.execute(
        select(LLMSlot).where(
            LLMSlot.school_id.is_(None),
            LLMSlot.slot_number == slot,
            LLMSlot.is_enabled.is_(True),
        ).limit(1)
    )
    config = result.scalar_one_or_none()
    if config:
        logger.debug("llm_router: slot=%d → platform default (%s)", slot, config.model)
        return config.api_url, config.api_key, config.model

    # 3. .env fallback
    if settings.LLM_API_URL and settings.LLM_API_KEY:
        logger.debug("llm_router: slot=%d → .env fallback (%s)", slot, settings.LLM_MODEL)
        return settings.LLM_API_URL, settings.LLM_API_KEY, settings.LLM_MODEL

    raise NotFoundError(f"LLM Slot {slot} 未配置，且 .env 中无 LLM_API_URL")


def get_llm_config_sync(*, slot: int) -> tuple[str, str, str]:
    """同步版本 — 仅从 .env 读取（用于无 db session 的场景如 arq worker 启动）。"""
    if settings.LLM_API_URL and settings.LLM_API_KEY:
        return settings.LLM_API_URL, settings.LLM_API_KEY, settings.LLM_MODEL
    raise NotFoundError(f"LLM Slot {slot} 未配置")


# 槽位常量 — 代码中引用这些常量，不写魔法数字
SLOT_AI_CHAT = 1           # AI 对话分析
SLOT_AI_GRADING = 2        # AI 阅卷（视觉）
SLOT_ANSWER_STANDARDIZE = 3  # 答案标准化
SLOT_RESERVED_4 = 4        # 预留
SLOT_RESERVED_5 = 5        # 预留
SLOT_RESERVED_6 = 6        # 预留
