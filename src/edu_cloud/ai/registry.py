"""Tool registration and discovery (Design §4)."""
from __future__ import annotations

import inspect
import logging
from dataclasses import dataclass, field
from typing import Any, Awaitable, Callable

from edu_cloud.ai.tool_context import ToolContext, ToolResult

logger = logging.getLogger(__name__)


@dataclass
class ToolSpec:
    name: str
    description: str
    parameters: dict
    func: Callable[[dict, ToolContext], Awaitable[ToolResult]]
    category: str = "general"
    module_code: str | None = None
    domain: str = "general"
    requires_capabilities: list[tuple[str, str]] = field(default_factory=list)
    risk_level: str = "low"
    allowed_roles: list[str] | None = None
    is_read_only: bool = True
    sensitivity: str = "school"  # "public" | "school" | "student"


class ToolRegistry:
    def __init__(self):
        self._tools: dict[str, ToolSpec] = {}

    def register(
        self,
        name: str,
        description: str,
        parameters: dict | None = None,
        category: str = "general",
        module_code: str | None = None,
        domain: str = "general",
        requires_capabilities: list[tuple] | None = None,
        risk_level: str = "low",
        allowed_roles: list[str] | None = None,
        is_read_only: bool = True,
        sensitivity: str = "school",
    ):
        def decorator(func: Callable):
            self._tools[name] = ToolSpec(
                name=name,
                description=description,
                parameters=parameters or {},
                func=func,
                category=category,
                module_code=module_code,
                domain=domain,
                requires_capabilities=list(requires_capabilities or []),
                risk_level=risk_level,
                allowed_roles=allowed_roles,
                is_read_only=is_read_only,
                sensitivity=sensitivity,
            )
            return func
        return decorator

    def list_tools(self) -> list[str]:
        return list(self._tools.keys())

    def get(self, name: str) -> ToolSpec | None:
        return self._tools.get(name)

    def get_all_specs(self) -> list[ToolSpec]:
        return list(self._tools.values())

    def filter_by_names(self, names: list[str]) -> list["ToolSpec"]:
        """Return ToolSpecs matching the given names, in the order of names."""
        return [self._tools[n] for n in names if n in self._tools]

    def get_schemas(self, categories: list[str] | None = None) -> list[dict]:
        """Return tool schemas filtered by category.

        Args:
            categories: ``None`` → all tools; ``[]`` → no tools (access denied);
                        ``["cat1", ...]`` → only matching tools.
        """
        result = []
        for spec in self._tools.values():
            if categories is not None and spec.category not in categories:
                continue
            # If parameters already has "type"/"properties" keys, it's a full
            # JSON Schema (legacy registration). Otherwise wrap it.
            params = spec.parameters
            if not (isinstance(params, dict) and "type" in params and "properties" in params):
                params = {"type": "object", "properties": params}
            result.append({
                "type": "function",
                "function": {
                    "name": spec.name,
                    "description": spec.description,
                    "parameters": params,
                },
            })
        return result

    @staticmethod
    def _is_new_style(func: Callable) -> bool:
        """Check if func matches new-style (input: dict, ctx: ToolContext) signature."""
        sig = inspect.signature(func)
        params = [p for p in sig.parameters.values()
                  if p.kind in (p.POSITIONAL_ONLY, p.POSITIONAL_OR_KEYWORD)]
        return len(params) == 2 and not params[0].name.startswith("_")

    async def execute(self, name: str, arguments: dict[str, Any], ctx_or_none=None, **injected) -> Any:
        spec = self._tools.get(name)
        if spec is None:
            if isinstance(ctx_or_none, ToolContext):
                return ToolResult(success=False, error=f"Unknown tool: {name}")
            return {"error": f"Unknown tool: {name}"}
        try:
            # Determine call style: signature-based (not caller-based) to handle
            # ToolExecutor always passing ToolContext even for legacy tools.
            if isinstance(ctx_or_none, ToolContext) and self._is_new_style(spec.func):
                # New-style call: func(input, ctx) -> ToolResult
                result = spec.func(arguments, ctx_or_none)
                if inspect.isawaitable(result):
                    result = await result
                return result
            else:
                # Legacy call: func(**kwargs) -> dict (backward compat until Batch 6)
                # When called with ToolContext, extract injected params from it.
                func = spec.func
                sig = inspect.signature(func)
                kwargs = {}
                for param_name, param in sig.parameters.items():
                    if param_name.startswith("_"):
                        if isinstance(ctx_or_none, ToolContext):
                            if param_name == "_db":
                                kwargs["_db"] = ctx_or_none.db
                            elif param_name == "_school_id":
                                kwargs["_school_id"] = ctx_or_none.school_id
                            elif param_name == "_user_id":
                                kwargs["_user_id"] = ctx_or_none.user_id
                        elif param_name in injected:
                            kwargs[param_name] = injected[param_name]
                    elif param_name in arguments:
                        kwargs[param_name] = arguments[param_name]
                if inspect.iscoroutinefunction(func):
                    return await func(**kwargs)
                return func(**kwargs)
        except Exception as exc:
            logger.exception("Tool %s execution failed", name)
            if isinstance(ctx_or_none, ToolContext):
                return ToolResult(success=False, error=str(exc))
            return {"error": str(exc)}


# Global registry instance
tools = ToolRegistry()
