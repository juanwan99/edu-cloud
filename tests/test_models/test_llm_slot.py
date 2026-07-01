"""LLMSlot model + slot_selector tests."""
import pytest
from edu_cloud.models.llm_slot import LLMSlot
from edu_cloud.config import settings
from edu_cloud.modules.exam.slot_selector import get_llm_config, get_llm_config_sync
from edu_cloud.services.exceptions import NotFoundError


@pytest.mark.asyncio
async def test_school_slot_overrides_platform_default(db):
    """学校级 slot 优先于平台默认。"""
    platform = LLMSlot(
        slot_number=1, api_url="http://platform", api_key="pk", model="m-platform",
    )
    school = LLMSlot(
        slot_number=1, school_id="school-A", api_url="http://school", api_key="sk", model="m-school",
    )
    db.add_all([platform, school])
    await db.commit()

    url, key, model = await get_llm_config(db, slot=1, school_id="school-A")
    assert url == "http://school"
    assert model == "m-school"


@pytest.mark.asyncio
async def test_fallback_to_platform_when_no_school_slot(db):
    """无学校 slot 时 fallback 到平台默认。"""
    platform = LLMSlot(
        slot_number=1, api_url="http://platform", api_key="pk", model="m-platform",
    )
    db.add(platform)
    await db.commit()

    url, key, model = await get_llm_config(db, slot=1, school_id="school-B")
    assert url == "http://platform"
    assert model == "m-platform"


@pytest.mark.asyncio
async def test_disabled_slot_skipped(db):
    """Disabled governed slots fail closed instead of falling back to .env."""
    slot = LLMSlot(
        slot_number=1, api_url="http://disabled", api_key="dk", model="m-disabled",
        is_enabled=False,
    )
    db.add(slot)
    await db.commit()

    with pytest.raises(NotFoundError, match="no enabled school or platform configuration"):
        await get_llm_config(db, slot=1)


@pytest.mark.asyncio
async def test_governed_lookup_fails_when_no_slots(db):
    """Governed slot lookup must not bypass slot governance via .env defaults."""
    with pytest.raises(NotFoundError, match="no enabled school or platform configuration"):
        await get_llm_config(db, slot=99)


def test_sync_helper_keeps_explicit_env_only_behavior():
    """The sync helper is explicitly env-only and does not represent slot governance."""
    url, key, model = get_llm_config_sync(slot=99)
    assert url == settings.LLM_API_URL
    assert key == settings.LLM_API_KEY
    assert model == settings.LLM_MODEL


@pytest.mark.asyncio
async def test_duplicate_platform_defaults_no_crash(db):
    """重复平台默认槽位（school_id=NULL）不会导致 MultipleResultsFound。"""
    slot1 = LLMSlot(
        slot_number=1, api_url="http://dup1", api_key="k1", model="m1",
    )
    slot2 = LLMSlot(
        slot_number=1, api_url="http://dup2", api_key="k2", model="m2",
    )
    db.add_all([slot1, slot2])
    await db.commit()

    # Should return one of them, not crash
    url, key, model = await get_llm_config(db, slot=1)
    assert url in ("http://dup1", "http://dup2")
