"""LLM 模型槽位管理路由 — 从 exam-ai 迁入。"""
import logging

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from edu_cloud.database import get_db
from edu_cloud.api.deps import get_current_user
from edu_cloud.core.models.llm_slot import LLMSlot

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/llm-config", tags=["llm-config"])


def _slot_response(s: LLMSlot) -> dict:
    return {
        "id": s.id, "school_id": s.school_id, "slot_number": s.slot_number,
        "api_url": s.api_url,
        "api_key": s.api_key[:8] + "***" if s.api_key else None,
        "model": s.model, "label": s.label, "description": s.description,
        "is_enabled": s.is_enabled,
    }


@router.get("/slots")
async def list_slots(
    db: AsyncSession = Depends(get_db),
    current: dict = Depends(get_current_user),
):
    """列出当前学校可见的所有槽位（平台默认 + 学校覆盖）。"""
    school_id = current["current_role"].school_id

    result = await db.execute(
        select(LLMSlot).where(LLMSlot.school_id.is_(None)).order_by(LLMSlot.slot_number)
    )
    platform_slots = {s.slot_number: _slot_response(s) for s in result.scalars().all()}

    result = await db.execute(
        select(LLMSlot).where(LLMSlot.school_id == school_id).order_by(LLMSlot.slot_number)
    )
    school_slots = {s.slot_number: _slot_response(s) for s in result.scalars().all()}

    slots = []
    for num in range(1, 7):
        slots.append({
            "slot_number": num,
            "platform_default": platform_slots.get(num),
            "school_override": school_slots.get(num),
            "effective": school_slots.get(num) or platform_slots.get(num),
        })
    return {"slots": slots}


class SlotUpsert(BaseModel):
    slot_number: int
    api_url: str
    api_key: str
    model: str
    label: str | None = None
    description: str | None = None
    is_enabled: bool = True


@router.put("/slots")
async def upsert_slot(
    req: SlotUpsert,
    db: AsyncSession = Depends(get_db),
    current: dict = Depends(get_current_user),
):
    """创建或更新学校级槽位配置。"""
    role = current["current_role"]
    if role.role not in ("platform_admin", "principal", "academic_director"):
        raise HTTPException(403, "仅管理员可配置 LLM 模型")
    if not 1 <= req.slot_number <= 6:
        raise HTTPException(400, "槽位号必须在 1-6 之间")

    school_id = role.school_id
    result = await db.execute(
        select(LLMSlot).where(LLMSlot.school_id == school_id, LLMSlot.slot_number == req.slot_number)
    )
    existing = result.scalar_one_or_none()

    if existing:
        existing.api_url = req.api_url
        existing.api_key = req.api_key
        existing.model = req.model
        existing.label = req.label
        existing.description = req.description
        existing.is_enabled = req.is_enabled
        await db.commit()
        await db.refresh(existing)
        logger.info("update_llm_slot: school=%s, slot=%d", school_id, req.slot_number)
        return _slot_response(existing)

    slot = LLMSlot(
        school_id=school_id, slot_number=req.slot_number,
        api_url=req.api_url, api_key=req.api_key, model=req.model,
        label=req.label, description=req.description, is_enabled=req.is_enabled,
    )
    db.add(slot)
    await db.commit()
    await db.refresh(slot)
    logger.info("create_llm_slot: school=%s, slot=%d", school_id, req.slot_number)
    return _slot_response(slot)


@router.delete("/slots/{slot_number}")
async def delete_slot(
    slot_number: int,
    db: AsyncSession = Depends(get_db),
    current: dict = Depends(get_current_user),
):
    """删除学校级槽位配置（回退到平台默认）。"""
    role = current["current_role"]
    if role.role not in ("platform_admin", "principal", "academic_director"):
        raise HTTPException(403, "仅管理员可配置 LLM 模型")

    result = await db.execute(
        select(LLMSlot).where(LLMSlot.school_id == role.school_id, LLMSlot.slot_number == slot_number)
    )
    slot = result.scalar_one_or_none()
    if not slot:
        raise HTTPException(404, "该槽位无学校级配置")

    await db.delete(slot)
    await db.commit()
    logger.info("delete_llm_slot: school=%s, slot=%d", role.school_id, slot_number)
    return {"deleted": True, "slot_number": slot_number}
