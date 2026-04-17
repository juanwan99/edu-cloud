"""Tests for dual-model slot resolution — F003 wiring."""
import pytest
from edu_cloud.models.llm_slot import LLMSlot
from edu_cloud.modules.exam.slot_selector import resolve_agent_slots


@pytest.mark.asyncio
async def test_standard_and_advanced_separated(db):
    """Slots are split by tier: standard → user_slots, advanced → system_slots."""
    db.add_all([
        LLMSlot(slot_number=1, school_id="sch1", api_url="http://u", api_key="k",
                model="deepseek", tier="standard", is_enabled=True),
        LLMSlot(slot_number=2, school_id="sch1", api_url="http://s", api_key="k",
                model="claude", tier="advanced", is_enabled=True),
    ])
    await db.commit()

    user_slots, system_slots = await resolve_agent_slots(db, school_id="sch1")
    assert len(user_slots) == 1
    assert user_slots[0].model == "deepseek"
    assert len(system_slots) == 1
    assert system_slots[0].model == "claude"


@pytest.mark.asyncio
async def test_no_slots_returns_empty(db):
    """No slots for school → both lists empty."""
    user_slots, system_slots = await resolve_agent_slots(db, school_id="nonexistent")
    assert user_slots == []
    assert system_slots == []


@pytest.mark.asyncio
async def test_disabled_slots_excluded(db):
    """Disabled slots are not returned."""
    db.add(LLMSlot(slot_number=1, school_id="sch1", api_url="http://u", api_key="k",
                   model="deepseek", tier="standard", is_enabled=False))
    await db.commit()

    user_slots, system_slots = await resolve_agent_slots(db, school_id="sch1")
    assert user_slots == []


@pytest.mark.asyncio
async def test_null_tier_treated_as_standard(db):
    """Slot with tier=None defaults to standard (user_slots)."""
    db.add(LLMSlot(slot_number=1, school_id="sch1", api_url="http://u", api_key="k",
                   model="deepseek", tier=None, is_enabled=True))
    await db.commit()

    user_slots, system_slots = await resolve_agent_slots(db, school_id="sch1")
    assert len(user_slots) == 1
    assert system_slots == []


@pytest.mark.asyncio
async def test_platform_defaults_included_when_no_school_slots(db):
    """Platform-level slots (school_id=None) are used as fallback."""
    db.add(LLMSlot(slot_number=1, api_url="http://platform", api_key="k",
                   model="gpt-4", tier="standard", is_enabled=True))
    await db.commit()

    user_slots, system_slots = await resolve_agent_slots(db, school_id="sch1")
    assert len(user_slots) == 1
    assert user_slots[0].model == "gpt-4"


@pytest.mark.asyncio
async def test_school_overrides_platform_same_slot_number(db):
    """School slot overrides platform default for same slot_number."""
    db.add_all([
        LLMSlot(slot_number=1, api_url="http://platform", api_key="k",
                model="platform-model", tier="standard", is_enabled=True),
        LLMSlot(slot_number=1, school_id="sch1", api_url="http://school", api_key="k",
                model="school-model", tier="standard", is_enabled=True),
    ])
    await db.commit()

    user_slots, system_slots = await resolve_agent_slots(db, school_id="sch1")
    assert len(user_slots) == 1
    assert user_slots[0].model == "school-model"
