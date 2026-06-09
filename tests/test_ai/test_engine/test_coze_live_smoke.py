"""Optional live smoke for a configured Coze provider.

Set AI_COZE_LIVE_SMOKE=1 and the normal AI_COZE_* settings to verify that the
provider can stream a real answer. This test is intentionally skipped in normal
CI and local runs because it depends on external Coze credentials.
"""
from __future__ import annotations

import os

import pytest

from edu_cloud.ai.providers.base import AgentProviderContext
from edu_cloud.ai.providers.coze import CozeProvider
from edu_cloud.config import settings


class _NoopDb:
    def add(self, obj):
        return None

    async def commit(self):
        return None


class _NoopSessionmaker:
    def __call__(self):
        return self

    async def __aenter__(self):
        return _NoopDb()

    async def __aexit__(self, exc_type, exc, tb):
        return None


pytestmark = pytest.mark.skipif(
    os.getenv("AI_COZE_LIVE_SMOKE") != "1",
    reason="Set AI_COZE_LIVE_SMOKE=1 to run the live Coze smoke test",
)


@pytest.mark.asyncio
async def test_coze_provider_live_smoke_streams_answer():
    provider = CozeProvider(settings)
    status_bits = {
        "AI_COZE_ENABLED": settings.AI_COZE_ENABLED,
        "AI_COZE_API_BASE": bool(settings.AI_COZE_API_BASE),
        "AI_COZE_BOT_ID": bool(settings.AI_COZE_BOT_ID),
        "AI_COZE_API_TOKEN": bool(settings.AI_COZE_API_TOKEN),
    }
    assert provider.is_available(), f"Coze provider is not configured: {status_bits}"

    ctx = AgentProviderContext(
        db_sessionmaker=_NoopSessionmaker(),
        user_id="live-smoke-user",
        school_id="live-smoke-school",
        role="subject_teacher",
        data_scope=None,
        enabled_modules=frozenset(),
        capabilities={},
        anonymizer=None,
        memory=None,
        session_id="coze-live-smoke",
        system_prompt="",
        tool_meta_registry={},
        tool_functions=[],
        tool_names=[],
        provider_state={},
    )
    run = await provider.create_run(ctx)

    events = [event async for event in run.run("请用一句中文回复：Coze live smoke OK")]
    event_types = [event.type for event in events]

    assert "error" not in event_types
    assert "answer" in event_types
    assert event_types[-1] == "done"
