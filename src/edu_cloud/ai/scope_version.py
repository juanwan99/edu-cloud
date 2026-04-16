"""ScopeVersionChecker — DB-persisted scope invalidation.

Each user×school pair has a version number (default 1 when no DB record exists).
When assignments/roles change, bump() increments the version so stale DataScope
snapshots can be detected and tool calls can request a refresh.
"""
from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import select, update

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

from edu_cloud.models.scope_version import ScopeVersion


class ScopeVersionChecker:
    """Check and bump scope versions backed by the scope_versions table."""

    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def get_current_version(self, school_id: str, user_id: str) -> int:
        """Get current version from DB. No record -> return 1 (initial)."""
        row = (
            await self._db.execute(
                select(ScopeVersion.version).where(
                    ScopeVersion.school_id == school_id,
                    ScopeVersion.user_id == user_id,
                )
            )
        ).scalar_one_or_none()
        return row if row is not None else 1

    async def is_valid(self, school_id: str, user_id: str, version: int) -> bool:
        """Check if given version >= current. No record -> valid (version=1)."""
        current = await self.get_current_version(school_id, user_id)
        return version >= current

    async def bump(self, school_id: str, user_id: str, reason: str) -> int:
        """Increment version. Create record if needed (version=2). Return new version."""
        row = (
            await self._db.execute(
                select(ScopeVersion).where(
                    ScopeVersion.school_id == school_id,
                    ScopeVersion.user_id == user_id,
                )
            )
        ).scalar_one_or_none()

        if row is None:
            row = ScopeVersion(
                school_id=school_id,
                user_id=user_id,
                version=2,
                last_reason=reason,
            )
            self._db.add(row)
        else:
            row.version += 1
            row.last_reason = reason

        await self._db.flush()
        return row.version

    async def bump_school(self, school_id: str, reason: str) -> None:
        """Bump all users in a school (semester switch etc)."""
        await self._db.execute(
            update(ScopeVersion)
            .where(ScopeVersion.school_id == school_id)
            .values(
                version=ScopeVersion.version + 1,
                last_reason=reason,
            )
        )
        await self._db.flush()
