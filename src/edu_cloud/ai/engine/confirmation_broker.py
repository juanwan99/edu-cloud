"""ConfirmationBroker — in-memory write confirmation for deferred tools.

Production version will use SSE + REST endpoint with 5-minute timeout.
This Step 2 version uses an in-memory dict for testing and development.
"""
from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)

DEFAULT_TIMEOUT = 300.0  # 5 minutes


TIMEOUT_BY_RISK: dict[str, float] = {"low": 120.0}


@dataclass(slots=True)
class PendingConfirmation:
    tool_call_id: str
    tool_name: str
    args: dict[str, Any]
    timeout: float = DEFAULT_TIMEOUT
    requested_at: float = field(default_factory=time.monotonic)
    resolved: bool = False
    approved: bool = False
    resolved_at: float | None = None


class ConfirmationBroker:
    """Manages deferred tool confirmations within an agent run.

    In Step 2 (in-memory): confirmations are stored in a dict and
    resolved programmatically or via auto-approve for testing.

    In production: will integrate with SSE push + REST callback.
    """

    def __init__(self, timeout: float = DEFAULT_TIMEOUT, auto_approve: bool = False):
        self._pending: dict[str, PendingConfirmation] = {}
        self._timeout = timeout
        self._auto_approve = auto_approve
        self._events: dict[str, asyncio.Event] = {}

    def request_confirmation(
        self,
        tool_call_id: str,
        tool_name: str,
        args: dict[str, Any],
        risk_level: str = "medium",
    ) -> PendingConfirmation:
        """Register a pending write operation that needs teacher approval."""
        pc = PendingConfirmation(
            tool_call_id=tool_call_id,
            tool_name=tool_name,
            args=args,
            timeout=TIMEOUT_BY_RISK.get(risk_level, self._timeout) if risk_level != "medium" else self._timeout,
        )
        self._pending[tool_call_id] = pc
        self._events[tool_call_id] = asyncio.Event()

        if self._auto_approve:
            self.approve(tool_call_id)

        return pc

    def approve(self, tool_call_id: str) -> None:
        """Approve a pending confirmation."""
        pc = self._pending.get(tool_call_id)
        if pc and not pc.resolved:
            pc.resolved = True
            pc.approved = True
            pc.resolved_at = time.monotonic()
            event = self._events.get(tool_call_id)
            if event:
                event.set()

    def deny(self, tool_call_id: str) -> None:
        """Deny a pending confirmation."""
        pc = self._pending.get(tool_call_id)
        if pc and not pc.resolved:
            pc.resolved = True
            pc.approved = False
            pc.resolved_at = time.monotonic()
            event = self._events.get(tool_call_id)
            if event:
                event.set()

    async def wait_for_resolution(self, tool_call_id: str) -> bool:
        """Wait until the confirmation is resolved or times out. Returns approved status."""
        event = self._events.get(tool_call_id)
        if not event:
            return False

        try:
            await asyncio.wait_for(event.wait(), timeout=self._timeout)
        except asyncio.TimeoutError:
            self.deny(tool_call_id)

        pc = self._pending.get(tool_call_id)
        return pc.approved if pc else False

    def get_pending(self) -> list[PendingConfirmation]:
        return [pc for pc in self._pending.values() if not pc.resolved]

    def is_expired(self, tool_call_id: str) -> bool:
        pc = self._pending.get(tool_call_id)
        if not pc:
            return True
        return (time.monotonic() - pc.requested_at) > pc.timeout

    def purge_resolved(self) -> int:
        """Remove resolved/expired entries to prevent memory growth."""
        now = time.monotonic()
        stale = [
            cid for cid, pc in self._pending.items()
            if pc.resolved or (now - pc.requested_at) > pc.timeout
        ]
        for cid in stale:
            self._pending.pop(cid, None)
            self._events.pop(cid, None)
        return len(stale)
