"""Tenant isolation helpers shared across routers."""

from dataclasses import dataclass
from fastapi import HTTPException
from sqlalchemy import false as sa_false

CROSS_SCHOOL_ROLES: frozenset[str] = frozenset({"platform_admin", "district_admin"})
# school_admin is school-scoped (not cross-school) — intentionally excluded


def get_school_id(current: dict) -> str | None:
    """Return school_id from JWT for tenant isolation.

    platform_admin / district_admin see all schools (returns None).
    All other roles are scoped to their own school_id.
    Raises 403 if non-admin role has no school_id (fail-closed).
    """
    role = current["current_role"].role
    if role in CROSS_SCHOOL_ROLES:
        return None
    school_id = current["current_role"].school_id
    if not school_id:
        raise HTTPException(403, "Role has no school_id")
    return school_id


@dataclass(frozen=True, slots=True)
class TenantContext:
    user_id: str
    role_id: str
    role_name: str
    school_id: str | None
    visible_class_ids: tuple[str, ...] | None
    visible_subject_codes: tuple[str, ...] | None

    def require_school(self) -> str:
        if self.school_id is None:
            raise HTTPException(403, "School scope required")
        return self.school_id

    def apply_school(self, stmt, model):
        if self.school_id is not None:
            stmt = stmt.where(getattr(model, "school_id") == self.school_id)
        return stmt

    def apply_subject_scope(self, stmt, column):
        if self.visible_subject_codes is None:
            return stmt
        if len(self.visible_subject_codes) == 0:
            return stmt.where(sa_false())
        return stmt.where(column.in_(self.visible_subject_codes))

    def apply_class_scope(self, stmt, column):
        if self.visible_class_ids is None:
            return stmt
        if len(self.visible_class_ids) == 0:
            return stmt.where(sa_false())
        return stmt.where(column.in_(self.visible_class_ids))
