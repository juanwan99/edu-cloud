"""Workflow registry — step/workflow definitions and lookup."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Coroutine

StepFunc = Callable[..., Coroutine[Any, Any, dict | None]]


@dataclass
class StepDefinition:
    name: str
    func: StepFunc
    compensate: StepFunc | None = None  # optional compensation function


@dataclass
class WorkflowDefinition:
    name: str
    steps: list[StepDefinition]
    max_retries: int = 3


class WorkflowRegistry:
    def __init__(self) -> None:
        self._workflows: dict[str, WorkflowDefinition] = {}

    def register(self, wf: WorkflowDefinition) -> None:
        if wf.name in self._workflows:
            raise ValueError(f"Workflow '{wf.name}' already registered")
        self._workflows[wf.name] = wf

    def get(self, name: str) -> WorkflowDefinition | None:
        return self._workflows.get(name)

    def list_all(self) -> list[str]:
        return list(self._workflows.keys())
