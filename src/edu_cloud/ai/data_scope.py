"""DataScope: frozen capture of what data a user can see.

DataScopeBuilder derives it from the user's role and assignments in the DB.
Fail-closed: unknown roles raise DataScopeBuildError instead of defaulting.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import TYPE_CHECKING

from sqlalchemy import select

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

from edu_cloud.models.guardian import GuardianStudentLink
from edu_cloud.models.school_settings import SchoolSetting
from edu_cloud.models.teacher_assignment import TeacherAssignment
from edu_cloud.models.user_role import UserRole


# ── Persona map ───────────────────────────────────────────────────

PERSONA_MAP: dict[str, str] = {
    "platform_admin": "admin_analyst",
    "district_admin": "admin_analyst",
    "school_admin": "school_leader",
    "principal": "school_leader",
    "academic_director": "teacher_assistant",
    "grade_leader": "teacher_assistant",
    "homeroom_teacher": "teacher_assistant",
    "subject_teacher": "teacher_assistant",
    "teaching_research_leader": "teacher_assistant",
    "lesson_prep_leader": "teacher_assistant",
    "parent": "parent_advisor",
}


# ── Exceptions ────────────────────────────────────────────────────


class DataScopeBuildError(Exception):
    """Raised when a DataScope cannot be built (missing data, unknown role, etc.)."""


# ── DataScope (frozen) ────────────────────────────────────────────


@dataclass(frozen=True)
class DataScope:
    """Immutable snapshot of a user's data visibility."""

    user_id: str
    school_id: str
    role: str

    # None = no limit (full access within school / cross-school)
    visible_class_ids: list[str] | None
    visible_subject_codes: list[str] | None
    visible_grade_ids: list[str] | None
    visible_student_ids: list[str] | None  # parent: [child_id, ...]
    district_ids: list[str] | None  # district_admin only

    can_write: bool
    can_see_rankings: bool
    can_cross_school: bool
    persona: str  # teacher_assistant / parent_advisor / admin_analyst / school_leader
    version: int
    computed_at: datetime | None = field(default=None)


# ── DataScopeBuilder ─────────────────────────────────────────────


class DataScopeBuilder:
    """Derive a DataScope from the DB for a given user + role."""

    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def build(self, user_id: str, role_id: str) -> DataScope:
        """Build a DataScope for *user_id* using the UserRole identified by *role_id*.

        Raises DataScopeBuildError on any inconsistency.
        """
        # 1. Fetch UserRole
        role_row = (
            await self._db.execute(select(UserRole).where(UserRole.id == role_id))
        ).scalars().first()
        if role_row is None:
            raise DataScopeBuildError(f"UserRole not found: {role_id}")
        if role_row.user_id != user_id:
            raise DataScopeBuildError(
                f"user_id mismatch: role belongs to {role_row.user_id}, got {user_id}"
            )

        # 2. Persona lookup (fail-closed)
        role_str: str = role_row.role
        persona = PERSONA_MAP.get(role_str)
        if persona is None:
            raise DataScopeBuildError(
                f"Unknown role '{role_str}' not in PERSONA_MAP — fail-closed"
            )

        school_id: str = role_row.school_id or ""

        # 3. Role-specific derivation
        if role_str == "platform_admin":
            return self._make(
                user_id=user_id,
                school_id=school_id,
                role=role_str,
                persona=persona,
                can_write=True,
                can_see_rankings=True,
                can_cross_school=True,
            )

        if role_str == "district_admin":
            district_ids = getattr(role_row, "district_ids", None) or []
            return self._make(
                user_id=user_id,
                school_id=school_id,
                role=role_str,
                persona=persona,
                district_ids=district_ids,
                can_write=True,
                can_see_rankings=True,
                can_cross_school=True,
            )

        if role_str in ("school_admin", "principal"):
            return self._make(
                user_id=user_id,
                school_id=school_id,
                role=role_str,
                persona=persona,
                can_write=True,
                can_see_rankings=True,
            )

        if role_str == "academic_director":
            return self._make(
                user_id=user_id,
                school_id=school_id,
                role=role_str,
                persona=persona,
                can_write=True,
                can_see_rankings=True,
            )

        if role_str == "grade_leader":
            grade_ids = role_row.grade_ids or []
            class_ids: list[str] = []
            if grade_ids:
                from edu_cloud.modules.student.models import Class
                stmt = select(Class.id).where(
                    Class.grade_id.in_(grade_ids),
                    Class.school_id == school_id,
                )
                class_ids = list((await self._db.execute(stmt)).scalars().all())
            return self._make(
                user_id=user_id,
                school_id=school_id,
                role=role_str,
                persona=persona,
                visible_class_ids=class_ids,
                visible_grade_ids=grade_ids,
                can_write=True,
                can_see_rankings=True,
            )


        if role_str == "teaching_research_leader":
            return self._make(
                user_id=user_id,
                school_id=school_id,
                role=role_str,
                persona=persona,
                visible_subject_codes=role_row.subject_codes or [],
                can_write=True,
                can_see_rankings=True,
            )

        if role_str == "lesson_prep_leader":
            return self._make(
                user_id=user_id,
                school_id=school_id,
                role=role_str,
                persona=persona,
                visible_class_ids=role_row.class_ids or None,
                visible_subject_codes=role_row.subject_codes or [],
                visible_grade_ids=role_row.grade_ids or [],
                can_write=True,
                can_see_rankings=True,
            )

        if role_str == "homeroom_teacher":
            return await self._build_homeroom(user_id, school_id, role_row, persona)

        if role_str == "subject_teacher":
            return await self._build_subject_teacher(user_id, school_id, role_row, persona)

        if role_str == "parent":
            return await self._build_parent(user_id, school_id, role_row, persona)

        # Should be unreachable (PERSONA_MAP gate), but fail-closed anyway
        raise DataScopeBuildError(f"Unhandled role: {role_str}")  # pragma: no cover

    def build_from_override(
        self,
        *,
        impersonator_id: str,
        effective_role: str,
        school_id: str,
        scope_override: dict,
    ) -> DataScope:
        """Build DataScope directly from impersonation claims (no DB lookup).

        Used when JWT contains is_impersonation=True. The scope is fully
        specified in the token, so we skip UserRole/TeacherAssignment queries.
        """
        persona = PERSONA_MAP.get(effective_role)
        if persona is None:
            raise DataScopeBuildError(
                f"Cannot impersonate unknown role '{effective_role}'"
            )

        return self._make(
            user_id=impersonator_id,
            school_id=school_id,
            role=effective_role,
            persona=persona,
            visible_class_ids=scope_override.get("class_ids"),
            visible_subject_codes=scope_override.get("subject_codes"),
            visible_grade_ids=scope_override.get("grade_ids"),
            # NOTE: full write access during impersonation.
            # Future: add mode param to restrict to read-only.
            can_write=True,
            can_see_rankings=True,
            can_cross_school=(effective_role in ("platform_admin", "district_admin")),
        )

    # ── private helpers ───────────────────────────────────────────

    async def _build_homeroom(
        self, user_id: str, school_id: str, role_row: UserRole, persona: str
    ) -> DataScope:
        homeroom_ids: list[str] = role_row.class_ids or []

        # Union with TeacherAssignment class_ids
        stmt = select(TeacherAssignment).where(
            TeacherAssignment.user_id == user_id,
            TeacherAssignment.school_id == school_id,
            TeacherAssignment.is_active.is_(True),
        )
        assignments = (await self._db.execute(stmt)).scalars().all()
        assignment_class_ids = [a.class_id for a in assignments]
        subject_codes = sorted(set(a.subject_code for a in assignments))

        all_class_ids = sorted(set(homeroom_ids + assignment_class_ids))

        return self._make(
            user_id=user_id,
            school_id=school_id,
            role=role_row.role,
            persona=persona,
            visible_class_ids=all_class_ids or None,
            visible_subject_codes=subject_codes or None,
            can_write=True,
            can_see_rankings=True,
        )

    async def _build_subject_teacher(
        self, user_id: str, school_id: str, role_row: UserRole, persona: str
    ) -> DataScope:
        stmt = select(TeacherAssignment).where(
            TeacherAssignment.user_id == user_id,
            TeacherAssignment.school_id == school_id,
            TeacherAssignment.is_active.is_(True),
        )
        assignments = (await self._db.execute(stmt)).scalars().all()
        class_ids = sorted(set(a.class_id for a in assignments))
        subject_codes = sorted(set(a.subject_code for a in assignments))

        return self._make(
            user_id=user_id,
            school_id=school_id,
            role=role_row.role,
            persona=persona,
            visible_class_ids=class_ids or None,
            visible_subject_codes=subject_codes or None,
            can_write=True,
            can_see_rankings=True,
        )

    async def _build_parent(
        self, user_id: str, school_id: str, role_row: UserRole, persona: str
    ) -> DataScope:
        stmt = select(GuardianStudentLink.student_id).where(
            GuardianStudentLink.guardian_user_id == user_id,
            GuardianStudentLink.school_id == school_id,
        )
        rows = (await self._db.execute(stmt)).scalars().all()
        student_ids = list(rows)

        can_see_rankings = await self._get_setting(
            school_id, "parent_can_see_ranking", default=False
        )

        return self._make(
            user_id=user_id,
            school_id=school_id,
            role=role_row.role,
            persona=persona,
            visible_student_ids=student_ids,  # [] = deny-all (fail-closed), never None for parent
            can_write=False,
            can_see_rankings=can_see_rankings,
        )

    async def _get_setting(self, school_id: str, key: str, default: bool) -> bool:
        """Read a boolean school setting, returning *default* if missing."""
        stmt = select(SchoolSetting.value).where(
            SchoolSetting.school_id == school_id,
            SchoolSetting.key == key,
        )
        value = (await self._db.execute(stmt)).scalars().first()
        if value is None:
            return default
        return value.lower() in ("true", "1", "yes")

    @staticmethod
    def _make(
        *,
        user_id: str,
        school_id: str,
        role: str,
        persona: str,
        visible_class_ids: list[str] | None = None,
        visible_subject_codes: list[str] | None = None,
        visible_grade_ids: list[str] | None = None,
        visible_student_ids: list[str] | None = None,
        district_ids: list[str] | None = None,
        can_write: bool = False,
        can_see_rankings: bool = False,
        can_cross_school: bool = False,
    ) -> DataScope:
        return DataScope(
            user_id=user_id,
            school_id=school_id,
            role=role,
            visible_class_ids=visible_class_ids,
            visible_subject_codes=visible_subject_codes,
            visible_grade_ids=visible_grade_ids,
            visible_student_ids=visible_student_ids,
            district_ids=district_ids,
            can_write=can_write,
            can_see_rankings=can_see_rankings,
            can_cross_school=can_cross_school,
            persona=persona,
            version=1,
            computed_at=datetime.now(timezone.utc),
        )
