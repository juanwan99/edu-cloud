import pytest
from unittest.mock import AsyncMock
from edu_cloud.ai.model_router import ModelRouter
from edu_cloud.ai.registry import ToolSpec


def _make_spec(name, risk_level="low", domain="general"):
    return ToolSpec(
        name=name, description="", parameters={}, func=AsyncMock(),
        risk_level=risk_level, domain=domain,
    )


def test_high_risk_selects_advanced():
    router = ModelRouter()
    tools = [_make_spec("danger", risk_level="high")]
    tier = router.select(["exam"], tools)
    assert tier == "advanced"


def test_three_domains_selects_advanced():
    router = ModelRouter()
    tools = [_make_spec("t1")]
    tier = router.select(["exam", "student", "analytics"], tools)
    assert tier == "advanced"


def test_complex_combo_selects_advanced():
    router = ModelRouter()
    tools = [_make_spec("t1")]
    tier = router.select(["analytics", "profile"], tools)
    assert tier == "advanced"


def test_default_selects_standard():
    router = ModelRouter()
    tools = [_make_spec("t1")]
    tier = router.select(["exam"], tools)
    assert tier == "standard"


def test_empty_domains_selects_standard():
    router = ModelRouter()
    tools = [_make_spec("t1")]
    tier = router.select([], tools)
    assert tier == "standard"


# --- LLM Factory tests ---

@pytest.mark.asyncio
async def test_tier_null_compat(db_engine):
    """tier=NULL 的 slot 被 standard 查询命中"""
    from sqlalchemy.ext.asyncio import AsyncSession
    from edu_cloud.ai.llm_factory import create_llm_for_tier
    from edu_cloud.core.models.llm_slot import LLMSlot

    async with AsyncSession(db_engine) as session:
        slot = LLMSlot(
            slot_number=1, api_url="http://test/v1", api_key="k",
            model="gpt-test", is_enabled=True, school_id=None, tier=None,
        )
        session.add(slot)
        await session.commit()

        client = await create_llm_for_tier("standard", None, session)
        assert client.model == "gpt-test"
        await client.close()


@pytest.mark.asyncio
async def test_fallback_to_env(db_engine):
    """无匹配 slot 时 fallback 到 .env 配置"""
    from sqlalchemy.ext.asyncio import AsyncSession
    from edu_cloud.ai.llm_factory import create_llm_for_tier
    from edu_cloud.config import settings

    async with AsyncSession(db_engine) as session:
        client = await create_llm_for_tier("advanced", None, session)
        assert client.api_url == settings.LLM_API_URL.rstrip("/")
        assert client.model == settings.LLM_MODEL
        await client.close()
