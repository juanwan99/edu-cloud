import inspect
import logging
from typing import Any, Callable

logger = logging.getLogger(__name__)

class ToolRegistry:
    def __init__(self):
        self._tools: dict[str, dict] = {}

    def register(self, name: str, description: str, parameters: dict, category: str = "general"):
        def decorator(func: Callable):
            self._tools[name] = {"name": name, "description": description, "parameters": parameters, "category": category, "func": func}
            return func
        return decorator

    def list_tools(self) -> list[str]:
        return list(self._tools.keys())

    def get_schemas(self, categories: list[str] | None = None) -> list[dict]:
        result = []
        for tool in self._tools.values():
            if categories and tool["category"] not in categories:
                continue
            result.append({"type": "function", "function": {"name": tool["name"], "description": tool["description"], "parameters": tool["parameters"]}})
        return result

    async def execute(self, name: str, arguments: dict[str, Any], **injected) -> Any:
        if name not in self._tools:
            raise KeyError(f"Tool not found: {name}")
        func = self._tools[name]["func"]
        sig = inspect.signature(func)
        kwargs = dict(arguments)
        for param_name in sig.parameters:
            if param_name.startswith("_") and param_name in injected:
                kwargs[param_name] = injected[param_name]
        if inspect.iscoroutinefunction(func):
            return await func(**kwargs)
        return func(**kwargs)

# Global registry instance
tools = ToolRegistry()
