"""ScopedQuery: unified scope-aware data filter for AI tools.

Takes a DataScope and injects WHERE conditions into any SQLAlchemy SELECT query,
ensuring AI tools can only access data within the user's visibility boundary.
"""
from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from sqlalchemy import Select
    from sqlalchemy.ext.asyncio import AsyncSession

from edu_cloud.ai.data_scope import DataScope


class ScopeViolationError(Exception):
    """Request parameter exceeds DataScope boundary."""


class ScopedQuery:
    """Inject scope-based WHERE conditions into SQLAlchemy queries."""

    def __init__(self, db: AsyncSession, scope: DataScope) -> None:
        self.db = db
        self.scope = scope

    def apply(
        self,
        query: Select,
        model: Any,
        *,
        school_col: str = "school_id",
        class_col: str = "class_id",
        student_col: str = "student_id",
        subject_col: str = "subject_code",
    ) -> Select:
        """Auto-inject WHERE conditions based on scope."""
        # 1. school_id forced (unless can_cross_school)
        if not self.scope.can_cross_school and hasattr(model, school_col):
            query = query.where(getattr(model, school_col) == self.scope.school_id)

        # 2. district_ids
        if self.scope.district_ids is not None and hasattr(model, "district"):
            query = query.where(getattr(model, "district").in_(self.scope.district_ids))

        # 3. class_ids
        if self.scope.visible_class_ids is not None and hasattr(model, class_col):
            query = query.where(
                getattr(model, class_col).in_(self.scope.visible_class_ids)
            )

        # 4. subject_codes
        if self.scope.visible_subject_codes is not None and hasattr(model, subject_col):
            query = query.where(
                getattr(model, subject_col).in_(self.scope.visible_subject_codes)
            )

        # 5. student_ids (parent lock)
        if self.scope.visible_student_ids is not None and hasattr(model, student_col):
            query = query.where(
                getattr(model, student_col).in_(self.scope.visible_student_ids)
            )

        return query

    async def execute(
        self, query: Select, model: Any = None, **col_overrides: str
    ) -> list:
        """apply + execute in one step."""
        if model is not None:
            query = self.apply(query, model, **col_overrides)
        result = await self.db.execute(query)
        return result.all()

    def validate_param(self, param_name: str, value: str) -> None:
        """Validate request param doesn't exceed scope.

        Raises ScopeViolationError if the value is outside the allowed set.
        None in the scope means no limit (all values allowed).
        """
        checks: dict[str, list[str] | None] = {
            "class_id": self.scope.visible_class_ids,
            "subject_code": self.scope.visible_subject_codes,
            "student_id": self.scope.visible_student_ids,
        }
        allowed = checks.get(param_name)
        if allowed is not None and value not in allowed:
            raise ScopeViolationError(
                f"{param_name}={value} not in scope (allowed: {allowed})"
            )
