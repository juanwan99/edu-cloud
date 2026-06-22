"""PolicyToolGuardrail — three-layer hard boundary on every tool call.

Layer 1 (registration): RBAC role filter (done at Agent construction)
Layer 2 (before_tool): runtime RBAC + module + capability + scope + budget
Layer 3 (after_tool): budget debit + trace record + artifact handling
"""
from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from edu_cloud.ai.data_scope import DataScope
    from edu_cloud.ai.engine.budget import AgentBudget
    from edu_cloud.ai.engine.trace_recorder import TraceRecorder

from edu_cloud.ai.engine.tool_meta import EduToolMeta

logger = logging.getLogger(__name__)


class ToolDenied(Exception):
    """Raised when a tool call is rejected by policy."""

    def __init__(self, tool: str, reason: str, layer: str):
        self.tool = tool
        self.reason = reason
        self.layer = layer
        super().__init__(f"[{layer}] Tool '{tool}' denied: {reason}")


@dataclass(slots=True)
class ToolCallRecord:
    """Captures a single tool invocation for tracing."""

    tool_name: str
    meta: EduToolMeta
    args_fingerprint: str
    started_at: float = field(default_factory=time.monotonic)
    ended_at: float | None = None
    denied: bool = False
    deny_reason: str | None = None
    result_ref: str | None = None


class PolicyToolGuardrail:
    """The sole execution gateway. No tool runs without passing through here."""

    def __init__(
        self,
        role: str,
        enabled_modules: frozenset[str],
        capabilities: dict[tuple[str, str], bool],
        data_scope: DataScope,
        budget: AgentBudget,
        trace: TraceRecorder,
        tool_meta_registry: dict[str, EduToolMeta],
    ):
        self._role = role
        self._enabled_modules = enabled_modules
        self._capabilities = capabilities
        self._data_scope = data_scope
        self._budget = budget
        self._trace = trace
        self._meta_registry = tool_meta_registry

    def get_meta(self, tool_name: str) -> EduToolMeta | None:
        return self._meta_registry.get(tool_name)

    async def before_tool(
        self, meta: EduToolMeta, args: dict[str, Any]
    ) -> ToolCallRecord:
        """Pre-execution hard checks. Raises ToolDenied on any violation."""
        record = ToolCallRecord(
            tool_name=meta.name,
            meta=meta,
            args_fingerprint=_fingerprint(args),
        )

        try:
            self._check_role(meta)
            self._check_module(meta)
            self._check_capability(meta)
            self._check_scope(meta, args)
            self._budget.check_tool_call(is_write=not meta.is_read_only)
        except ToolDenied as td:
            record.denied = True
            record.deny_reason = td.reason
            self._trace.record_event("tool_denied", {
                "tool": td.tool, "layer": td.layer, "reason": td.reason,
            })
            raise
        except Exception as exc:
            record.denied = True
            record.deny_reason = str(exc)
            self._trace.record_event("tool_denied", {
                "tool": meta.name, "layer": "unknown", "reason": str(exc),
            })
            raise ToolDenied(meta.name, str(exc), "unknown") from exc

        return record

    async def after_tool(
        self, record: ToolCallRecord, result: Any
    ) -> Any:
        """Post-execution: budget debit + trace recording."""
        record.ended_at = time.monotonic()
        self._budget.debit_tool_call(is_write=not record.meta.is_read_only)
        self._trace.record_tool_call(record, result)
        return result

    # ── Layer checks ──

    def _check_role(self, meta: EduToolMeta) -> None:
        if meta.allowed_roles and self._role not in meta.allowed_roles:
            raise ToolDenied(
                meta.name,
                f"role '{self._role}' not in {meta.allowed_roles}",
                "rbac",
            )

    def _check_module(self, meta: EduToolMeta) -> None:
        if meta.module_code and meta.module_code not in self._enabled_modules:
            raise ToolDenied(
                meta.name,
                f"module '{meta.module_code}' not enabled",
                "module",
            )
        for module_code in meta.requires_modules:
            if module_code not in self._enabled_modules:
                raise ToolDenied(
                    meta.name,
                    f"module '{module_code}' not enabled",
                    "module",
                )

    def _check_capability(self, meta: EduToolMeta) -> None:
        for cap in meta.requires_capabilities:
            if not self._capabilities.get(cap, False):
                raise ToolDenied(
                    meta.name,
                    f"capability {cap} not granted",
                    "capability",
                )

    def _check_scope(self, meta: EduToolMeta, args: dict[str, Any]) -> None:
        if not self._data_scope.can_cross_school:
            arg_school = args.get("school_id")
            if arg_school and arg_school != self._data_scope.school_id:
                raise ToolDenied(
                    meta.name,
                    "cross-school access denied",
                    "scope",
                )

        if not self._data_scope.can_write and not meta.is_read_only:
            raise ToolDenied(
                meta.name,
                "write denied for this role/scope",
                "scope",
            )


def _fingerprint(args: dict[str, Any]) -> str:
    """Deterministic hash of tool arguments for trace deduplication."""
    import hashlib
    import json

    raw = json.dumps(args, sort_keys=True, default=str)
    return hashlib.sha256(raw.encode()).hexdigest()[:16]
