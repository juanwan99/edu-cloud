"""Tool wrapper — bridges old ToolSpec tools to Pydantic AI @agent.tool pattern.

Provides edu_tool() decorator that:
1. Registers EduToolMeta for PolicyToolGuardrail
2. Wraps the function with before_tool/after_tool policy enforcement
3. Handles DB session lifecycle (per-tool independent session)
4. Processes results through ArtifactManager
5. Pushes tool_call/tool_result events to AgentDeps.event_queue for SSE streaming
"""
from __future__ import annotations

import functools
import json
import logging
from typing import Any, Callable, Literal

from pydantic_ai import RunContext

from edu_cloud.ai.engine.agent_deps import AgentDeps
from edu_cloud.ai.engine.tool_meta import EduToolMeta

logger = logging.getLogger(__name__)

TOOL_META_REGISTRY: dict[str, EduToolMeta] = {}


def _safe_serialize_args(kwargs: dict) -> dict:
    """Best-effort serialize tool args for SSE — returns JSON-safe values."""
    out = {}
    for k, v in kwargs.items():
        try:
            safe = json.loads(json.dumps(v, ensure_ascii=False, default=str))
            out[k] = safe
        except (TypeError, ValueError):
            out[k] = str(v)
    return out


def edu_tool(
    *,
    name: str,
    module_code: str | None = None,
    domain: str = "general",
    risk_level: Literal["low", "medium", "high", "critical"] = "low",
    is_read_only: bool = True,
    allowed_roles: frozenset[str] | None = None,
    requires_capabilities: frozenset[tuple[str, str]] | None = None,
    requires_modules: frozenset[str] | None = None,
    sensitivity: Literal["public", "school", "class", "student", "pii"] = "school",
    artifact_policy: Literal["inline", "auto", "always"] = "auto",
) -> Callable:
    """Decorator for edu-cloud Pydantic AI tools.

    Usage:
        @edu_tool(name="get_class_list", module_code="exam", ...)
        async def get_class_list(ctx: RunContext[AgentDeps], grade: str | None = None) -> str:
            async with ctx.deps.get_db() as db:
                ...
            return json.dumps(result)
    """
    meta = EduToolMeta(
        name=name,
        module_code=module_code,
        domain=domain,
        risk_level=risk_level,
        is_read_only=is_read_only,
        allowed_roles=allowed_roles or frozenset(),
        requires_capabilities=requires_capabilities or frozenset(),
        requires_modules=requires_modules or frozenset(),
        sensitivity=sensitivity,
        artifact_policy=artifact_policy,
    )
    TOOL_META_REGISTRY[name] = meta

    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        async def wrapper(ctx: RunContext[AgentDeps], *args: Any, **kwargs: Any) -> str:
            from edu_cloud.ai.schemas import AgentEvent

            q = ctx.deps.event_queue
            try:
                record = await ctx.deps.policy.before_tool(meta, kwargs)
            except Exception:
                if q is not None:
                    await q.put(AgentEvent(
                        type="tool_result",
                        data={"tool": name, "error": True, "denied": True},
                    ))
                raise

            if q is not None:
                await q.put(AgentEvent(
                    type="tool_call",
                    data={"tool": name, "arguments": _safe_serialize_args(kwargs)},
                ))

            try:
                result = await func(ctx, *args, **kwargs)

                if hasattr(ctx.deps, "anonymizer") and ctx.deps.anonymizer:
                    try:
                        if isinstance(result, str):
                            _data = json.loads(result)
                            _data = ctx.deps.anonymizer.anonymize(_data)
                            result = json.dumps(_data, ensure_ascii=False)
                        elif isinstance(result, (dict, list)):
                            result = ctx.deps.anonymizer.anonymize(result)
                    except Exception as anon_err:
                        logger.error("anonymization failed for tool %s: %s", name, anon_err)
                        result = "[data redacted: anonymization error]"

                processed = ctx.deps.artifacts.process_result(
                    name, result, sensitivity,
                )
                if isinstance(processed, dict) and processed.get("_artifact"):
                    result = json.dumps(processed, ensure_ascii=False)
                elif not isinstance(result, str):
                    result = json.dumps(result, ensure_ascii=False, default=str)

                await ctx.deps.policy.after_tool(record, result)

                if q is not None:
                    await q.put(AgentEvent(
                        type="tool_result",
                        data={"tool": name},
                    ))

                return result
            except Exception:
                record.ended_at = __import__("time").monotonic()
                record.denied = True
                if q is not None:
                    await q.put(AgentEvent(
                        type="tool_result",
                        data={"tool": name, "error": True},
                    ))
                raise

        wrapper.__name__ = func.__name__
        wrapper.__doc__ = func.__doc__
        wrapper._edu_meta = meta
        return wrapper

    return decorator


def get_all_tool_metas() -> dict[str, EduToolMeta]:
    """Return the global registry of tool metadata."""
    return dict(TOOL_META_REGISTRY)
