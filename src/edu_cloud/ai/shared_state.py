"""Shared state container for AgentTeam sub-agents."""
from __future__ import annotations
import copy
from typing import Any


class SharedState:
    """Mutable key-value state shared among sub-agents within a team.
    Tracks history of all writes for audit/debugging.
    NOT thread-safe — designed for sequential or cooperative async execution.
    """
    def __init__(self) -> None:
        self._data: dict[str, Any] = {}
        self._history: list[tuple[str, Any]] = []
        self._stage: str | None = None

    def get(self, key: str, default: Any = None) -> Any:
        return self._data.get(key, default)

    def set(self, key: str, value: Any) -> None:
        self._data[key] = value
        self._history.append((key, value))

    def get_history(self) -> list[tuple[str, Any]]:
        return list(self._history)

    def checkpoint(self) -> dict[str, Any]:
        return copy.deepcopy(self._data)

    def restore(self, snapshot: dict[str, Any]) -> None:
        self._data = copy.deepcopy(snapshot)

    def as_dict(self) -> dict[str, Any]:
        return copy.deepcopy(self._data)

    @property
    def current_stage(self) -> str | None:
        return self._stage

    def set_stage(self, stage: str) -> None:
        self._stage = stage
