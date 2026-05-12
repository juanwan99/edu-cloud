"""AgentBudget — request-level hard limits on agent resource consumption."""
from __future__ import annotations

import time
from dataclasses import dataclass, field


class BudgetExhausted(Exception):
    """Raised when any budget dimension is exceeded."""

    def __init__(self, dimension: str, limit: int | float, current: int | float):
        self.dimension = dimension
        self.limit = limit
        self.current = current
        super().__init__(f"Budget exhausted: {dimension} ({current}/{limit})")


@dataclass(slots=True)
class AgentBudget:
    """Mutable counters with hard ceilings. Fail-closed on any breach."""

    max_tokens: int = 100_000
    max_tool_calls: int = 50
    max_write_ops: int = 10
    max_wall_clock_seconds: float = 300.0

    used_tokens: int = field(default=0, init=False)
    used_tool_calls: int = field(default=0, init=False)
    used_write_ops: int = field(default=0, init=False)
    _start_time: float = field(default_factory=time.monotonic, init=False)

    def check_tool_call(self, *, is_write: bool = False) -> None:
        """Pre-flight check before executing a tool. Raises BudgetExhausted."""
        elapsed = time.monotonic() - self._start_time
        if elapsed > self.max_wall_clock_seconds:
            raise BudgetExhausted("wall_clock", self.max_wall_clock_seconds, elapsed)
        if self.used_tool_calls >= self.max_tool_calls:
            raise BudgetExhausted("tool_calls", self.max_tool_calls, self.used_tool_calls)
        if is_write and self.used_write_ops >= self.max_write_ops:
            raise BudgetExhausted("write_ops", self.max_write_ops, self.used_write_ops)

    def debit_tool_call(self, *, is_write: bool = False) -> None:
        """Record a completed tool call."""
        self.used_tool_calls += 1
        if is_write:
            self.used_write_ops += 1

    def debit_tokens(self, count: int) -> None:
        """Record token usage. Raises BudgetExhausted if over limit."""
        self.used_tokens += count
        if self.used_tokens > self.max_tokens:
            raise BudgetExhausted("tokens", self.max_tokens, self.used_tokens)

    def snapshot(self) -> dict:
        """Current state for trace recording."""
        return {
            "tokens": f"{self.used_tokens}/{self.max_tokens}",
            "tool_calls": f"{self.used_tool_calls}/{self.max_tool_calls}",
            "write_ops": f"{self.used_write_ops}/{self.max_write_ops}",
            "elapsed_s": round(time.monotonic() - self._start_time, 1),
        }
