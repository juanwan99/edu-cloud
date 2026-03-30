import inspect
import logging
from dataclasses import dataclass, field
from typing import Any, Callable

logger = logging.getLogger(__name__)


@dataclass
class ToolSpec:
    name: str
    description: str
    parameters: dict
    func: Callable
    category: str = "general"
    module_code: str | None = None
    domain: str = "general"
    requires_capabilities: list[tuple[str, str]] = field(default_factory=list)
    risk_level: str = "low"
    allowed_roles: list[str] | None = None


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
    ):
        def decorator(func: Callable):
            self._tools[name] = ToolSpec(
                name=name,
                description=description,
                parameters=parameters or {"type": "object", "properties": {}},
                func=func,
                category=category,
                module_code=module_code,
                domain=domain,
                requires_capabilities=requires_capabilities or [],
                risk_level=risk_level,
                allowed_roles=allowed_roles,
            )
            return func
        return decorator

    def list_tools(self) -> list[str]:
        return list(self._tools.keys())

    def get_all_specs(self) -> list[ToolSpec]:
        return list(self._tools.values())

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
            result.append({"type": "function", "function": {"name": spec.name, "description": spec.description, "parameters": spec.parameters}})
        return result

    async def execute(self, name: str, arguments: dict[str, Any], **injected) -> Any:
        if name not in self._tools:
            return {"error": f"Unknown tool: {name}"}
        spec = self._tools[name]
        func = spec.func
        sig = inspect.signature(func)
        kwargs = {}
        for param_name, param in sig.parameters.items():
            if param_name.startswith("_"):
                if param_name in injected:
                    kwargs[param_name] = injected[param_name]
            elif param_name in arguments:
                kwargs[param_name] = arguments[param_name]
        if inspect.iscoroutinefunction(func):
            return await func(**kwargs)
        return func(**kwargs)


# Global registry instance
tools = ToolRegistry()
