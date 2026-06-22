import json
from datetime import datetime
from unittest.mock import AsyncMock

import pytest

from edu_cloud.ai.data_scope import DataScope
from edu_cloud.ai.engine.artifact_manager import ArtifactManager
from edu_cloud.ai.engine.tool_wrapper import edu_tool
from edu_cloud.ai.engine.trace_recorder import TraceRecorder
from edu_cloud.ai.providers.base import AgentProviderContext
from edu_cloud.ai.tool_gateway import (
    ToolGatewayError,
    describe_context_tools,
    describe_registered_tools,
    execute_registered_tool,
    register_tool_context,
)
from edu_cloud.api.ai_internal import _check_service_token
from fastapi import HTTPException


@edu_tool(name="gateway_test_read", module_code="exam", domain="test", allowed_roles=frozenset({"subject_teacher"}))
async def gateway_test_read(ctx, value: str) -> str:
    return json.dumps({"value": value, "role": ctx.deps.role})


@edu_tool(
    name="gateway_test_write",
    module_code="exam",
    domain="test",
    allowed_roles=frozenset({"subject_teacher"}),
    is_read_only=False,
    risk_level="medium",
)
async def gateway_test_write(ctx, value: str) -> str:
    return json.dumps({"value": value})


def _context(tool_functions):
    metas = {
        getattr(fn, "_edu_meta").name: getattr(fn, "_edu_meta")
        for fn in tool_functions
    }
    scope = DataScope(
        user_id="u1",
        school_id="s1",
        role="subject_teacher",
        visible_class_ids=["c1"],
        visible_subject_codes=["math"],
        visible_grade_ids=None,
        visible_student_ids=None,
        district_ids=None,
        can_write=True,
        can_see_rankings=True,
        can_cross_school=False,
        persona="teacher_assistant",
        version=1,
        computed_at=datetime.now(),
    )
    return AgentProviderContext(
        db_sessionmaker=lambda: None,
        user_id="u1",
        school_id="s1",
        role="subject_teacher",
        data_scope=scope,
        enabled_modules=frozenset({"exam"}),
        capabilities={},
        anonymizer=None,
        memory=None,
        session_id="sess1",
        system_prompt="",
        tool_meta_registry=metas,
        tool_functions=tool_functions,
        tool_names=list(metas),
        provider_state={},
    )


@pytest.mark.asyncio
async def test_tool_gateway_executes_read_tool(monkeypatch):
    monkeypatch.setattr(TraceRecorder, "flush_to_db", AsyncMock())
    monkeypatch.setattr(ArtifactManager, "flush_to_db", AsyncMock())
    token = register_tool_context(_context([gateway_test_read]))

    result = await execute_registered_tool(
        context_token=token,
        tool_name="gateway_test_read",
        arguments={"value": "ok"},
    )

    assert result["status"] == "ok"
    assert result["result"] == {"value": "ok", "role": "subject_teacher"}


@pytest.mark.asyncio
async def test_tool_gateway_blocks_write_tool_until_confirmation():
    token = register_tool_context(_context([gateway_test_write]))

    result = await execute_registered_tool(
        context_token=token,
        tool_name="gateway_test_write",
        arguments={"value": "nope"},
    )

    assert result["status"] == "confirmation_required"
    assert "confirmation_id" in result
    assert result["tool"] == "gateway_test_write"
    assert result["arguments"] == {"value": "nope"}


@pytest.mark.asyncio
async def test_tool_gateway_executes_write_tool_after_confirmation(monkeypatch):
    monkeypatch.setattr(TraceRecorder, "flush_to_db", AsyncMock())
    monkeypatch.setattr(ArtifactManager, "flush_to_db", AsyncMock())
    token = register_tool_context(_context([gateway_test_write]))

    result = await execute_registered_tool(
        context_token=token,
        tool_name="gateway_test_write",
        arguments={"value": "yes"},
        allow_write=True,
    )

    assert result["status"] == "ok"
    assert result["result"] == {"value": "yes"}


def test_tool_gateway_describes_registered_tools():
    token = register_tool_context(_context([gateway_test_read]))

    result = describe_registered_tools(token)

    assert result["tools"][0]["name"] == "gateway_test_read"
    assert result["tools"][0]["is_read_only"] is True
    assert result["tools"][0]["requires_modules"] == []
    assert result["tools"][0]["parameters"]["required"] == ["value"]


def test_tool_gateway_describes_context_tools_without_registry_token():
    result = describe_context_tools(_context([gateway_test_read, gateway_test_write]))

    names = [tool["name"] for tool in result["tools"]]
    assert names == ["gateway_test_read", "gateway_test_write"]
    write_tool = next(tool for tool in result["tools"] if tool["name"] == "gateway_test_write")
    assert write_tool["is_read_only"] is False
    assert write_tool["risk_level"] == "medium"


@pytest.mark.asyncio
async def test_tool_gateway_denies_unavailable_tool():
    token = register_tool_context(_context([gateway_test_read]))

    with pytest.raises(ToolGatewayError, match="tool not available"):
        await execute_registered_tool(
            context_token=token,
            tool_name="missing_tool",
            arguments={},
        )


def test_internal_tool_route_requires_service_token(monkeypatch):
    from edu_cloud.config import settings

    # With the HTTP gateway enabled, a missing service token is still rejected.
    monkeypatch.setattr(settings, "AI_TOOL_GATEWAY_HTTP_ENABLED", True)
    monkeypatch.setattr(settings, "AI_TOOL_GATEWAY_TOKEN", "")
    with pytest.raises(HTTPException) as exc_info:
        _check_service_token(None)
    assert exc_info.value.status_code == 403


def test_internal_tool_route_fail_closed_when_http_disabled(monkeypatch):
    """F-001: even a correct token must be rejected while the HTTP gateway is off."""
    from edu_cloud.config import settings

    monkeypatch.setattr(settings, "AI_TOOL_GATEWAY_HTTP_ENABLED", False)
    monkeypatch.setattr(settings, "AI_TOOL_GATEWAY_TOKEN", "right-token")
    with pytest.raises(HTTPException) as exc_info:
        _check_service_token("right-token")
    assert exc_info.value.status_code == 403
    assert "disabled" in exc_info.value.detail.lower()


def test_internal_tool_route_rejects_wrong_token_when_enabled(monkeypatch):
    from edu_cloud.config import settings

    monkeypatch.setattr(settings, "AI_TOOL_GATEWAY_HTTP_ENABLED", True)
    monkeypatch.setattr(settings, "AI_TOOL_GATEWAY_TOKEN", "right-token")
    with pytest.raises(HTTPException) as exc_info:
        _check_service_token("wrong-token")
    assert exc_info.value.status_code == 403


def test_internal_tool_route_accepts_correct_token_when_enabled(monkeypatch):
    """Enabled gateway + correct token passes the service gate to reach context/tool checks."""
    from edu_cloud.config import settings

    monkeypatch.setattr(settings, "AI_TOOL_GATEWAY_HTTP_ENABLED", True)
    monkeypatch.setattr(settings, "AI_TOOL_GATEWAY_TOKEN", "right-token")
    assert _check_service_token("right-token") is None


@pytest.mark.asyncio
async def test_internal_tool_list_route_requires_service_token(client, monkeypatch):
    from edu_cloud.config import settings

    monkeypatch.setattr(settings, "AI_TOOL_GATEWAY_HTTP_ENABLED", True)
    monkeypatch.setattr(settings, "AI_TOOL_GATEWAY_TOKEN", "right-token")
    resp = await client.get("/internal/ai-tools", params={"context_token": "missing"})

    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_internal_tool_list_route_fail_closed_by_default(client, monkeypatch):
    """F-001 at the HTTP surface: default (disabled) returns 403 even with a correct token header."""
    from edu_cloud.config import settings

    monkeypatch.setattr(settings, "AI_TOOL_GATEWAY_HTTP_ENABLED", False)
    monkeypatch.setattr(settings, "AI_TOOL_GATEWAY_TOKEN", "right-token")
    resp = await client.get(
        "/internal/ai-tools",
        params={"context_token": "missing"},
        headers={"X-AI-Tool-Token": "right-token"},
    )

    assert resp.status_code == 403
    assert "disabled" in resp.json()["detail"].lower()


@pytest.mark.asyncio
async def test_internal_tool_list_route_disabled_missing_context_returns_403(client, monkeypatch):
    """F-001: disabled GET returns 403 *before* FastAPI query validation when context_token is missing.

    A malformed request (no context_token) must not surface the 422 query schema while the gateway
    is off; the disabled gate fails closed ahead of parameter validation.
    """
    from edu_cloud.config import settings

    monkeypatch.setattr(settings, "AI_TOOL_GATEWAY_HTTP_ENABLED", False)
    monkeypatch.setattr(settings, "AI_TOOL_GATEWAY_TOKEN", "right-token")
    resp = await client.get(
        "/internal/ai-tools",
        headers={"X-AI-Tool-Token": "right-token"},
    )

    assert resp.status_code == 403
    assert "disabled" in resp.json()["detail"].lower()


@pytest.mark.asyncio
async def test_internal_tool_exec_route_disabled_valid_body_returns_403(client, monkeypatch):
    """F-001 POST surface: disabled gateway returns 403 even for a well-formed body."""
    from edu_cloud.config import settings

    monkeypatch.setattr(settings, "AI_TOOL_GATEWAY_HTTP_ENABLED", False)
    monkeypatch.setattr(settings, "AI_TOOL_GATEWAY_TOKEN", "right-token")
    resp = await client.post(
        "/internal/ai-tools/some_tool",
        json={"context_token": "missing", "arguments": {}},
        headers={"X-AI-Tool-Token": "right-token"},
    )

    assert resp.status_code == 403
    assert "disabled" in resp.json()["detail"].lower()


@pytest.mark.asyncio
async def test_internal_tool_exec_route_disabled_missing_body_returns_403(client, monkeypatch):
    """F-001 POST surface: disabled returns 403 *before* body validation when the body is missing."""
    from edu_cloud.config import settings

    monkeypatch.setattr(settings, "AI_TOOL_GATEWAY_HTTP_ENABLED", False)
    monkeypatch.setattr(settings, "AI_TOOL_GATEWAY_TOKEN", "right-token")
    resp = await client.post(
        "/internal/ai-tools/some_tool",
        headers={"X-AI-Tool-Token": "right-token"},
    )

    assert resp.status_code == 403
    assert "disabled" in resp.json()["detail"].lower()


@pytest.mark.asyncio
async def test_internal_tool_exec_route_disabled_malformed_body_returns_403(client, monkeypatch):
    """F-001 POST surface: disabled returns 403 *before* body validation for malformed JSON."""
    from edu_cloud.config import settings

    monkeypatch.setattr(settings, "AI_TOOL_GATEWAY_HTTP_ENABLED", False)
    monkeypatch.setattr(settings, "AI_TOOL_GATEWAY_TOKEN", "right-token")
    resp = await client.post(
        "/internal/ai-tools/some_tool",
        content="{not valid json",
        headers={
            "X-AI-Tool-Token": "right-token",
            "Content-Type": "application/json",
        },
    )

    assert resp.status_code == 403
    assert "disabled" in resp.json()["detail"].lower()


@pytest.mark.asyncio
async def test_internal_tool_exec_route_enabled_reaches_gateway_logic(client, monkeypatch):
    """Non-regression: enabled + correct service token passes the disabled gate and reaches gateway
    context validation (403 'context not found', distinct from the disabled-state 403)."""
    from edu_cloud.config import settings

    monkeypatch.setattr(settings, "AI_TOOL_GATEWAY_HTTP_ENABLED", True)
    monkeypatch.setattr(settings, "AI_TOOL_GATEWAY_TOKEN", "right-token")
    resp = await client.post(
        "/internal/ai-tools/some_tool",
        json={"context_token": "missing", "arguments": {}},
        headers={"X-AI-Tool-Token": "right-token"},
    )

    assert resp.status_code == 403
    detail = resp.json()["detail"].lower()
    assert "disabled" not in detail
    assert "context" in detail


@pytest.mark.asyncio
async def test_internal_tool_exec_route_enabled_malformed_body_still_validates(client, monkeypatch):
    """Non-regression: when enabled, a malformed body still surfaces FastAPI's 422; the disabled
    gate only short-circuits while the gateway is off and never swallows real validation."""
    from edu_cloud.config import settings

    monkeypatch.setattr(settings, "AI_TOOL_GATEWAY_HTTP_ENABLED", True)
    monkeypatch.setattr(settings, "AI_TOOL_GATEWAY_TOKEN", "right-token")
    resp = await client.post(
        "/internal/ai-tools/some_tool",
        content="{not valid json",
        headers={
            "X-AI-Tool-Token": "right-token",
            "Content-Type": "application/json",
        },
    )

    assert resp.status_code == 422
