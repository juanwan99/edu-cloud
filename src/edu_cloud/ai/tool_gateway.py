"""Internal Tool Gateway for external agent providers.

External providers such as Coze must call back into edu-cloud for all business
data access. The gateway executes only tools registered for the current edu
context and keeps policy enforcement on the edu side.
"""
from __future__ import annotations

import json
import inspect
import time
import uuid
from dataclasses import dataclass, field
from typing import Any

from edu_cloud.ai.engine.agent_deps import AgentDeps
from edu_cloud.ai.engine.artifact_manager import ArtifactManager
from edu_cloud.ai.engine.budget import AgentBudget
from edu_cloud.ai.engine.confirmation_broker import ConfirmationBroker
from edu_cloud.ai.engine.policy_guardrail import PolicyToolGuardrail
from edu_cloud.ai.engine.trace_recorder import TraceRecorder
from edu_cloud.ai.memory_store import MemoryStore


@dataclass(slots=True)
class RegisteredToolContext:
    context: Any
    created_at: float = field(default_factory=time.monotonic)


_CONTEXTS: dict[str, RegisteredToolContext] = {}
_TTL_SECONDS = 3600.0


class ToolGatewayError(Exception):
    def __init__(self, message: str, status_code: int = 400) -> None:
        self.status_code = status_code
        super().__init__(message)


class _RunContextShim:
    def __init__(self, deps: AgentDeps) -> None:
        self.deps = deps


def register_tool_context(context: Any) -> str:
    purge_expired_tool_contexts()
    token = uuid.uuid4().hex
    _CONTEXTS[token] = RegisteredToolContext(context=context)
    return token


def purge_expired_tool_contexts() -> int:
    now = time.monotonic()
    stale = [key for key, value in _CONTEXTS.items() if now - value.created_at > _TTL_SECONDS]
    for key in stale:
        _CONTEXTS.pop(key, None)
    return len(stale)


async def execute_registered_tool(
    *,
    context_token: str,
    tool_name: str,
    arguments: dict[str, Any],
    allow_write: bool = False,
) -> dict[str, Any]:
    purge_expired_tool_contexts()
    registered = _CONTEXTS.get(context_token)
    if not registered:
        raise ToolGatewayError("tool context not found or expired", 403)

    context = registered.context
    tool = _find_tool(context.tool_functions, tool_name)
    meta = getattr(tool, "_edu_meta", None)
    if meta is None:
        raise ToolGatewayError("tool metadata missing", 500)
    if not meta.is_read_only and not allow_write:
        return {
            "status": "confirmation_required",
            "confirmation_id": uuid.uuid4().hex,
            "tool": tool_name,
            "arguments": arguments or {},
            "risk_level": meta.risk_level,
            "message": "write tools must be confirmed by edu-cloud before execution",
        }

    deps = _build_deps(context)
    result = await tool(_RunContextShim(deps), **(arguments or {}))
    deps.trace.flush()
    await deps.trace.flush_to_db(context.db_sessionmaker)
    await deps.artifacts.flush_to_db(context.db_sessionmaker)
    return {
        "status": "ok",
        "tool": tool_name,
        "result": _decode_result(result),
    }


def describe_registered_tools(context_token: str) -> dict[str, Any]:
    purge_expired_tool_contexts()
    registered = _CONTEXTS.get(context_token)
    if not registered:
        raise ToolGatewayError("tool context not found or expired", 403)
    return describe_context_tools(registered.context)


def describe_context_tools(context: Any) -> dict[str, Any]:
    tools = []
    for tool in context.tool_functions:
        meta = getattr(tool, "_edu_meta", None)
        if not meta:
            continue
        tools.append({
            "name": meta.name,
            "module_code": meta.module_code,
            "requires_modules": sorted(meta.requires_modules),
            "domain": meta.domain,
            "risk_level": meta.risk_level,
            "is_read_only": meta.is_read_only,
            "sensitivity": meta.sensitivity,
            "requires_capabilities": [list(cap) for cap in sorted(meta.requires_capabilities)],
            "parameters": _tool_parameters(tool),
            "description": (tool.__doc__ or "").strip().split("\n")[0],
        })
    return {"tools": tools}


def _find_tool(tool_functions: list[Any], tool_name: str) -> Any:
    for tool in tool_functions:
        meta = getattr(tool, "_edu_meta", None)
        if meta and meta.name == tool_name:
            return tool
    raise ToolGatewayError(f"tool not available in current context: {tool_name}", 403)


def _build_deps(context: Any) -> AgentDeps:
    run_id = uuid.uuid4().hex[:16]
    trace = TraceRecorder(run_id, context.session_id, context.school_id, context.user_id, context.role)
    budget = AgentBudget()
    artifacts = ArtifactManager(run_id, context.school_id, context.anonymizer)
    confirmations = ConfirmationBroker()
    policy = PolicyToolGuardrail(
        role=context.role,
        enabled_modules=context.enabled_modules,
        capabilities=context.capabilities,
        data_scope=context.data_scope,
        budget=budget,
        trace=trace,
        tool_meta_registry=context.tool_meta_registry,
    )
    return AgentDeps(
        run_id=run_id,
        request_id=uuid.uuid4().hex[:12],
        session_id=context.session_id,
        user_id=context.user_id,
        school_id=context.school_id,
        role=context.role,
        data_scope=context.data_scope,
        enabled_modules=context.enabled_modules,
        capabilities=context.capabilities,
        db_sessionmaker=context.db_sessionmaker,
        budget=budget,
        policy=policy,
        confirmations=confirmations,
        artifacts=artifacts,
        trace=trace,
        memory=context.memory or MemoryStore(),
        anonymizer=context.anonymizer,
        model_slot="tool-gateway",
    )


def _decode_result(result: Any) -> Any:
    if isinstance(result, str):
        try:
            return json.loads(result)
        except json.JSONDecodeError:
            return result
    return result


def _tool_parameters(tool: Any) -> dict[str, Any]:
    signature = inspect.signature(tool)
    properties: dict[str, Any] = {}
    required: list[str] = []
    for name, param in signature.parameters.items():
        if name in {"ctx", "context"}:
            continue
        properties[name] = {
            "type": _schema_type(param.annotation),
            "description": "",
        }
        if param.default is inspect.Parameter.empty:
            required.append(name)
    return {
        "type": "object",
        "properties": properties,
        "required": required,
    }


def _schema_type(annotation: Any) -> str:
    raw = str(annotation)
    if "list" in raw or "List" in raw:
        return "array"
    if "dict" in raw or "Dict" in raw:
        return "object"
    if "int" in raw:
        return "integer"
    if "float" in raw:
        return "number"
    if "bool" in raw:
        return "boolean"
    return "string"
