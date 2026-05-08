"""Tenant isolation helpers shared across routers."""

from fastapi import HTTPException

CROSS_SCHOOL_ROLES: frozenset[str] = frozenset({"platform_admin", "district_admin"})


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
