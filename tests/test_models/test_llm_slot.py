"""LLMSlot model + slot_selector tests."""
import pytest
from edu_cloud.core.models.llm_slot import LLMSlot
from edu_cloud.modules.exam.slot_selector import get_llm_config


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
    """disabled slot 不返回，fallback 到 .env。"""
    slot = LLMSlot(
        slot_number=1, api_url="http://disabled", api_key="dk", model="m-disabled",
        is_enabled=False,
    )
    db.add(slot)
    await db.commit()

    # Should fallback to .env (settings.LLM_API_URL is set in test env)
    url, key, model = await get_llm_config(db, slot=1)
    assert url != "http://disabled"


@pytest.mark.asyncio
async def test_env_fallback_when_no_slots(db):
    """数据库无任何 slot 时 fallback 到 .env。"""
    from edu_cloud.config import settings
    # settings has default LLM_API_URL set
    url, key, model = await get_llm_config(db, slot=99)
    assert url == settings.LLM_API_URL
    assert model == settings.LLM_MODEL
