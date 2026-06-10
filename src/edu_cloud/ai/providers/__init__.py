"""Provider selection for edu-cloud AI chat."""
from __future__ import annotations

from typing import Any

from edu_cloud.ai.providers.base import (
    AgentProviderContext,
    AgentProviderUnavailable,
    AgentRunHandle,
)
from edu_cloud.ai.providers.coze import CozeProvider
from edu_cloud.ai.providers.current_pydantic import CurrentPydanticProvider


def _providers(settings: Any) -> dict[str, Any]:
    return {
        "coze": CozeProvider(settings),
        "current_pydantic": CurrentPydanticProvider(),
        "pydantic": CurrentPydanticProvider(),
    }


def provider_status(settings: Any) -> dict[str, Any]:
    providers = _providers(settings)
    preferred = (settings.AI_AGENT_PROVIDER or "coze").lower()
    fallback = (settings.AI_AGENT_FALLBACK_PROVIDER or "current_pydantic").lower()
    active = _select_provider_name(providers, preferred, fallback)
    coze_ready = providers["coze"].is_available()
    gateway_public_base_configured = bool(getattr(settings, "AI_TOOL_GATEWAY_PUBLIC_BASE", ""))
    gateway_token_configured = bool(getattr(settings, "AI_TOOL_GATEWAY_TOKEN", ""))
    gateway_http_enabled = bool(getattr(settings, "AI_TOOL_GATEWAY_HTTP_ENABLED", False))
    required_action_submit_enabled = bool(
        getattr(settings, "AI_COZE_REQUIRED_ACTION_SUBMIT_ENABLED", False)
    )
    required_action_submit_ready = coze_ready and required_action_submit_enabled
    http_tool_gateway_ready = (
        coze_ready
        and gateway_http_enabled
        and gateway_public_base_configured
        and gateway_token_configured
    )
    return {
        "preferred": preferred,
        "fallback": fallback,
        "active": active,
        "available": {name: provider.is_available() for name, provider in providers.items()},
        "readiness": {
            "coze": {
                "ready": coze_ready,
                "chat_ready": coze_ready,
                "missing": _missing_coze_settings(settings),
                "tool_gateway_public_base_configured": gateway_public_base_configured,
                "tool_gateway_token_configured": gateway_token_configured,
                "tool_gateway_http_enabled": gateway_http_enabled,
                "tool_gateway_http_ready": http_tool_gateway_ready,
                "required_action_submit_enabled": required_action_submit_enabled,
                "required_action_submit_ready": required_action_submit_ready,
                "required_action_submit_endpoint": "/v3/chat/submit_tool_outputs",
                "tool_modes": {
                    "coze_required_action": required_action_submit_ready,
                    "http_tool_gateway": http_tool_gateway_ready,
                },
            }
        },
    }


async def create_agent_run(settings: Any, context: AgentProviderContext) -> AgentRunHandle:
    providers = _providers(settings)
    preferred = (settings.AI_AGENT_PROVIDER or "coze").lower()
    fallback = (settings.AI_AGENT_FALLBACK_PROVIDER or "current_pydantic").lower()
    selected = _select_provider_name(providers, preferred, fallback)
    return await providers[selected].create_run(context)


async def create_fallback_agent_run(settings: Any, context: AgentProviderContext) -> AgentRunHandle:
    providers = _providers(settings)
    fallback = (settings.AI_AGENT_FALLBACK_PROVIDER or "current_pydantic").lower()
    provider = providers.get(fallback)
    if provider and provider.is_available():
        return await provider.create_run(context)
    current = providers["current_pydantic"]
    if current.is_available():
        return await current.create_run(context)
    raise AgentProviderUnavailable("No fallback AI agent provider is available")


def _select_provider_name(providers: dict[str, Any], preferred: str, fallback: str) -> str:
    provider = providers.get(preferred)
    if provider and provider.is_available():
        return preferred
    fallback_provider = providers.get(fallback)
    if fallback_provider and fallback_provider.is_available():
        return fallback
    current = providers["current_pydantic"]
    if current.is_available():
        return "current_pydantic"
    raise AgentProviderUnavailable("No AI agent provider is available")


def _missing_coze_settings(settings: Any) -> list[str]:
    required = [
        ("AI_COZE_ENABLED", bool(getattr(settings, "AI_COZE_ENABLED", False))),
        ("AI_COZE_API_BASE", bool(getattr(settings, "AI_COZE_API_BASE", ""))),
        ("AI_COZE_BOT_ID", bool(getattr(settings, "AI_COZE_BOT_ID", ""))),
        ("AI_COZE_API_TOKEN", bool(getattr(settings, "AI_COZE_API_TOKEN", ""))),
    ]
    return [name for name, configured in required if not configured]
