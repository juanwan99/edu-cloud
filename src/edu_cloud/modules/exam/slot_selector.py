"""LLM route selection by governed slot number and optional school ID.

Priority: school override > platform default. Missing or disabled slots fail closed.
"""
import logging
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from edu_cloud.models.llm_slot import LLMSlot
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

    raise NotFoundError(f"LLM Slot {slot} has no enabled school or platform configuration")


def get_llm_config_sync(*, slot: int) -> tuple[str, str, str]:
    """同步版本 — 仅从 .env 读取（用于无 db session 的场景如 arq worker 启动）。"""
    if settings.LLM_API_URL and settings.LLM_API_KEY:
        return settings.LLM_API_URL, settings.LLM_API_KEY, settings.LLM_MODEL
    raise NotFoundError(f"LLM Slot {slot} 未配置")


async def resolve_agent_slots(
    db: AsyncSession, *, school_id: str,
) -> tuple[list[LLMSlot], list[LLMSlot]]:
    """按 tier 分组返回 (user_slots, system_slots)。

    user_slots: tier=standard 或 tier=None（用户自备模型）
    system_slots: tier=advanced（系统增强模型）

    优先级：学校覆盖 > 平台默认（按 slot_number 去重）。
    """
    # 1. 学校级 slots
    school_result = await db.execute(
        select(LLMSlot).where(
            LLMSlot.school_id == school_id,
            LLMSlot.is_enabled.is_(True),
        )
    )
    school_slots = list(school_result.scalars().all())

    # 2. 平台默认 slots（school_id=None），排除已被学校覆盖的 slot_number
    school_slot_numbers = {s.slot_number for s in school_slots}
    platform_result = await db.execute(
        select(LLMSlot).where(
            LLMSlot.school_id.is_(None),
            LLMSlot.is_enabled.is_(True),
        )
    )
    platform_slots = [
        s for s in platform_result.scalars().all()
        if s.slot_number not in school_slot_numbers
    ]

    # 3. 合并并按 tier 分组
    all_slots = school_slots + platform_slots
    user_slots = [s for s in all_slots if (s.tier or "standard") != "advanced"]
    system_slots = [s for s in all_slots if s.tier == "advanced"]

    return user_slots, system_slots


# 槽位常量 — 代码中引用这些常量，不写魔法数字
SLOT_AI_CHAT = 1           # AI 对话分析
SLOT_AI_GRADING = 2        # AI 阅卷（视觉）
SLOT_ANSWER_STANDARDIZE = 3  # 答案标准化
SLOT_RESERVED_4 = 4        # 预留
SLOT_RESERVED_5 = 5        # 预留
SLOT_RESERVED_6 = 6        # 预留
