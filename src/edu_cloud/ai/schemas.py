"""Agent 数据模型。"""
from __future__ import annotations
import json
from dataclasses import dataclass, field
from typing import Any


@dataclass
class ChatMessage:
    role: str  # system / user / assistant / tool
    content: str | None = None
    tool_calls: list[ToolCall] | None = None
    tool_call_id: str | None = None  # role=tool 时必填
    name: str | None = None  # role=tool 时的工具名

    def to_dict(self) -> dict:
        d: dict = {"role": self.role}
        if self.content is not None:
            d["content"] = self.content
        if self.tool_calls:
            d["tool_calls"] = [tc.to_openai() for tc in self.tool_calls]
        if self.tool_call_id:
            d["tool_call_id"] = self.tool_call_id
        if self.name:
            d["name"] = self.name
        return d


@dataclass
class ToolCall:
    id: str
    name: str
    arguments: dict[str, Any] = field(default_factory=dict)
    _raw: dict = field(default_factory=dict, repr=False)  # 保留原始数据，兼容 Gemini 等非标准字段

    @classmethod
    def from_openai(cls, raw: dict) -> ToolCall:
        func = raw["function"]
        args_str = func.get("arguments", "{}")
        try:
            args = json.loads(args_str) if isinstance(args_str, str) else args_str
        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid tool call arguments: {e}") from e
        return cls(id=raw["id"], name=func["name"], arguments=args, _raw=raw)

    def to_openai(self) -> dict:
        base = {
            "id": self.id,
            "type": "function",
            "function": {"name": self.name, "arguments": json.dumps(self.arguments, ensure_ascii=False)},
        }
        # 合并原始数据中的额外字段（如 Gemini 的 thought_signature）
        for key, val in self._raw.items():
            if key not in ("id", "type", "function"):
                base[key] = val
        return base


@dataclass
class AgentEvent:
    type: str  # answer / tool_call / tool_result / thinking / error / done
    data: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {"type": self.type, "data": self.data}
