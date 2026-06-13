from types import SimpleNamespace

import pytest

from edu_cloud.ai.providers import provider_status


def _settings(**overrides):
    base = dict(
        AI_AGENT_PROVIDER="coze",
        AI_AGENT_FALLBACK_PROVIDER="current_pydantic",
        AI_COZE_ENABLED=False,
        AI_COZE_API_BASE="http://localhost:8888",
        AI_COZE_BOT_ID="",
        AI_COZE_API_TOKEN="",
        AI_COZE_TIMEOUT=120,
        AI_COZE_REQUIRED_ACTION_SUBMIT_ENABLED=False,
        AI_TOOL_GATEWAY_PUBLIC_BASE="",
        AI_TOOL_GATEWAY_TOKEN="",
        AI_TOOL_GATEWAY_HTTP_ENABLED=False,
    )
    base.update(overrides)
    return SimpleNamespace(**base)


def test_settings_required_action_submit_defaults_false_and_binds_env(monkeypatch):
    """Real Settings env binding: AI_COZE_REQUIRED_ACTION_SUBMIT_ENABLED must
    default to false and read true only when the env var is explicitly set.

    Guards against the D-05 dead-switch regression where the field was missing
    from Settings and pydantic ``extra="ignore"`` silently dropped the env var.
    """
    from edu_cloud.config import Settings

    monkeypatch.delenv("AI_COZE_REQUIRED_ACTION_SUBMIT_ENABLED", raising=False)
    default_settings = Settings(_env_file=None)
    assert default_settings.AI_COZE_REQUIRED_ACTION_SUBMIT_ENABLED is False

    monkeypatch.setenv("AI_COZE_REQUIRED_ACTION_SUBMIT_ENABLED", "true")
    enabled_settings = Settings(_env_file=None)
    assert enabled_settings.AI_COZE_REQUIRED_ACTION_SUBMIT_ENABLED is True


def test_provider_status_falls_back_to_current_when_coze_unconfigured():
    status = provider_status(_settings())
    assert status["preferred"] == "coze"
    assert status["active"] == "current_pydantic"
    assert status["available"]["coze"] is False
    assert status["available"]["current_pydantic"] is True
    assert status["readiness"]["coze"]["missing"] == [
        "AI_COZE_ENABLED",
        "AI_COZE_BOT_ID",
        "AI_COZE_API_TOKEN",
    ]


def test_provider_status_selects_coze_when_configured():
    status = provider_status(_settings(
        AI_COZE_ENABLED=True,
        AI_COZE_BOT_ID="bot-1",
        AI_COZE_API_TOKEN="pat-test",
    ))
    assert status["active"] == "coze"
    assert status["available"]["coze"] is True
    assert status["readiness"]["coze"]["missing"] == []
    assert status["readiness"]["coze"]["chat_ready"] is True
    assert status["readiness"]["coze"]["required_action_submit_enabled"] is False
    assert status["readiness"]["coze"]["required_action_submit_ready"] is False
    assert status["readiness"]["coze"]["tool_modes"]["coze_required_action"] is False
    assert status["readiness"]["coze"]["tool_modes"]["http_tool_gateway"] is False


def test_provider_status_reports_required_action_ready_only_when_explicitly_enabled():
    status = provider_status(_settings(
        AI_COZE_ENABLED=True,
        AI_COZE_BOT_ID="bot-1",
        AI_COZE_API_TOKEN="pat-test",
        AI_COZE_REQUIRED_ACTION_SUBMIT_ENABLED=True,
    ))

    coze = status["readiness"]["coze"]
    assert coze["required_action_submit_enabled"] is True
    assert coze["required_action_submit_ready"] is True
    assert coze["required_action_submit_endpoint"] == "/v3/chat/submit_tool_outputs"
    assert coze["tool_modes"]["coze_required_action"] is True
    assert "pat-test" not in str(status)


def test_provider_status_reports_gateway_readiness_without_secret_values():
    status = provider_status(_settings(
        AI_COZE_ENABLED=True,
        AI_COZE_BOT_ID="bot-1",
        AI_COZE_API_TOKEN="pat-test",
        AI_TOOL_GATEWAY_PUBLIC_BASE="https://edu.example.com",
        AI_TOOL_GATEWAY_TOKEN="secret-token",
    ))

    coze = status["readiness"]["coze"]
    assert coze["tool_gateway_public_base_configured"] is True
    assert coze["tool_gateway_token_configured"] is True
    assert coze["tool_gateway_http_enabled"] is False
    assert coze["tool_gateway_http_ready"] is False
    assert coze["tool_modes"]["http_tool_gateway"] is False
    assert "secret-token" not in str(status)
    assert "pat-test" not in str(status)


def test_provider_status_reports_http_gateway_ready_only_when_explicitly_enabled():
    status = provider_status(_settings(
        AI_COZE_ENABLED=True,
        AI_COZE_BOT_ID="bot-1",
        AI_COZE_API_TOKEN="pat-test",
        AI_TOOL_GATEWAY_PUBLIC_BASE="https://edu.example.com",
        AI_TOOL_GATEWAY_TOKEN="secret-token",
        AI_TOOL_GATEWAY_HTTP_ENABLED=True,
    ))

    coze = status["readiness"]["coze"]
    assert coze["tool_gateway_http_enabled"] is True
    assert coze["tool_gateway_http_ready"] is True
    assert coze["tool_modes"]["http_tool_gateway"] is True
    assert "secret-token" not in str(status)
    assert "pat-test" not in str(status)


@pytest.mark.asyncio
async def test_create_fallback_agent_run_prefers_configured_fallback(monkeypatch):
    from edu_cloud.ai import providers
    from edu_cloud.ai.providers import create_fallback_agent_run

    class DummyProvider:
        def __init__(self, name, available=True):
            self.name = name
            self._available = available

        def is_available(self):
            return self._available

        async def create_run(self, context):
            return SimpleNamespace(provider_name=self.name)

    monkeypatch.setattr(
        providers,
        "_providers",
        lambda settings: {
            "coze": DummyProvider("coze"),
            "current_pydantic": DummyProvider("current_pydantic"),
            "custom_fallback": DummyProvider("custom_fallback"),
        },
    )

    run = await create_fallback_agent_run(
        _settings(AI_AGENT_FALLBACK_PROVIDER="custom_fallback"),
        context=None,
    )

    assert run.provider_name == "custom_fallback"


@pytest.mark.asyncio
async def test_create_fallback_agent_run_uses_current_when_configured_fallback_unavailable(monkeypatch):
    from edu_cloud.ai import providers
    from edu_cloud.ai.providers import create_fallback_agent_run

    class DummyProvider:
        def __init__(self, name, available=True):
            self.name = name
            self._available = available

        def is_available(self):
            return self._available

        async def create_run(self, context):
            return SimpleNamespace(provider_name=self.name)

    monkeypatch.setattr(
        providers,
        "_providers",
        lambda settings: {
            "coze": DummyProvider("coze"),
            "current_pydantic": DummyProvider("current_pydantic"),
            "custom_fallback": DummyProvider("custom_fallback", available=False),
        },
    )

    run = await create_fallback_agent_run(
        _settings(AI_AGENT_FALLBACK_PROVIDER="custom_fallback"),
        context=None,
    )

    assert run.provider_name == "current_pydantic"
