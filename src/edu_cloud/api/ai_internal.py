"""Internal AI tool gateway routes.

This router is intended for self-hosted agent providers such as Coze. It never
trusts provider-supplied identity or scope; callers must present a context token
issued by edu-cloud during the chat run.
"""
from __future__ import annotations

import hmac
from typing import Any

from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel, Field

from edu_cloud.ai.tool_gateway import ToolGatewayError, describe_registered_tools, execute_registered_tool
from edu_cloud.config import settings

router = APIRouter(prefix="/internal/ai-tools", tags=["ai-internal"])


class ToolGatewayRequest(BaseModel):
    context_token: str
    arguments: dict[str, Any] = Field(default_factory=dict)


@router.get("")
async def list_ai_tools(
    context_token: str,
    x_ai_tool_token: str | None = Header(default=None, alias="X-AI-Tool-Token"),
):
    _check_service_token(x_ai_tool_token)
    try:
        return describe_registered_tools(context_token)
    except ToolGatewayError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc


@router.post("/{tool_name}")
async def execute_ai_tool(
    tool_name: str,
    req: ToolGatewayRequest,
    x_ai_tool_token: str | None = Header(default=None, alias="X-AI-Tool-Token"),
):
    _check_service_token(x_ai_tool_token)
    try:
        return await execute_registered_tool(
            context_token=req.context_token,
            tool_name=tool_name,
            arguments=req.arguments,
        )
    except ToolGatewayError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc


def _check_service_token(token: str | None) -> None:
    # Fail-closed: the HTTP tool gateway is off unless explicitly enabled. The
    # routes stay registered, but a registered route is not a usable gateway —
    # a correct token must still be rejected while AI_TOOL_GATEWAY_HTTP_ENABLED
    # is false (F-001). The token checks below only run once the gateway is on.
    if not settings.AI_TOOL_GATEWAY_HTTP_ENABLED:
        raise HTTPException(status_code=403, detail="AI tool HTTP gateway is disabled")
    expected = settings.AI_TOOL_GATEWAY_TOKEN
    if not expected:
        raise HTTPException(status_code=403, detail="AI tool gateway token is required")
    if not token or not hmac.compare_digest(token, expected):
        raise HTTPException(status_code=403, detail="invalid AI tool gateway token")
