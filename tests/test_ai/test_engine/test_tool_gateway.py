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

    monkeypatch.setattr(settings, "AI_TOOL_GATEWAY_TOKEN", "")
    with pytest.raises(HTTPException) as exc_info:
        _check_service_token(None)
    assert exc_info.value.status_code == 403


@pytest.mark.asyncio
async def test_internal_tool_list_route_requires_service_token(client):
    resp = await client.get("/internal/ai-tools", params={"context_token": "missing"})

    assert resp.status_code == 403
