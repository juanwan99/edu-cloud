"""Standardized tool execution context and result types (Design §4)."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from edu_cloud.ai.grounded import DataSource


@dataclass
class ToolContext:
    """Injected into every tool call. Replaces the old _db/_school_id/**kwargs pattern."""

    db: AsyncSession
    school_id: str
    user_id: str
    role: str
    class_ids: list[str] | None = None
    subject_codes: list[str] | None = None
    grade_ids: list[str] | None = None
    capabilities: dict[tuple[str, str], bool] = field(default_factory=dict)
    enabled_modules: list[str] = field(default_factory=list)
    anonymizer: Any | None = None  # Anonymizer (avoid circular import)
    data_scope: Any | None = None  # DataScope (avoid circular import)


@dataclass
class ToolResult:
    """Unified return type for all tools."""

    success: bool
    data: dict | list | str | None = None
    error: str | None = None
    metadata: dict | None = None
    is_read_only: bool = True
    source: DataSource | None = None

    def to_dict(self) -> dict:
        d: dict[str, Any] = {"success": self.success, "data": self.data}
        if self.error is not None:
            d["error"] = self.error
        if self.metadata is not None:
            d["metadata"] = self.metadata
        if self.source is not None:
            d["source"] = self.source.to_dict()
        return d
