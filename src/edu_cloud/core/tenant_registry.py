"""Tenant isolation registry -- declares which models need automatic school_id filtering.

Phase: audit mode (log-only, no enforcement).

The registry auto-discovers tenant-scoped models by scanning SQLAlchemy mappers
for classes that either inherit TenantMixin or have a ``school_id`` column.
"""
from __future__ import annotations

import logging
from contextvars import ContextVar
from typing import Optional

logger = logging.getLogger("edu_cloud.tenant")

# ── Tenant context (per-request via ContextVar) ──────────────────────────

_tenant_school_id: ContextVar[Optional[str]] = ContextVar(
    "tenant_school_id", default=None
)

# Tenant isolation mode: "audit" (log only) or "enforce" (inject WHERE).
TENANT_MODE = "audit"


def set_tenant(school_id: str | None) -> None:
    """Set the current request's tenant school_id."""
    _tenant_school_id.set(school_id)


def get_tenant() -> str | None:
    """Get the current tenant school_id (None = cross-school / no auth)."""
    return _tenant_school_id.get()


def clear_tenant() -> None:
    """Clear tenant context at request end."""
    _tenant_school_id.set(None)


# ── Model discovery ──────────────────────────────────────────────────────

# Cache to avoid re-scanning mappers on every query.
_scoped_tables_cache: set[str] | None = None


def get_tenant_scoped_models() -> set[str]:
    """Return table names that are tenant-scoped (have a school_id column).

    Discovery strategy (ordered):
      1. Classes inheriting ``TenantMixin``
      2. Any mapped class with a ``school_id`` column attribute

    The result is cached after first call.
    """
    global _scoped_tables_cache
    if _scoped_tables_cache is not None:
        return _scoped_tables_cache

    from edu_cloud.models.base import Base, TenantMixin

    scoped: set[str] = set()
    for mapper in Base.registry.mappers:
        cls = mapper.class_
        tablename = getattr(cls, "__tablename__", None)
        if not tablename:
            continue

        # Path 1: explicit TenantMixin inheritance
        if issubclass(cls, TenantMixin):
            scoped.add(tablename)
            continue

        # Path 2: has a school_id column (many module models define it directly)
        if "school_id" in mapper.columns:
            scoped.add(tablename)

    _scoped_tables_cache = scoped
    logger.info(
        "tenant_registry: discovered %d tenant-scoped tables", len(scoped)
    )
    return scoped


def _reset_cache() -> None:
    """Reset the scoped-tables cache (for testing only)."""
    global _scoped_tables_cache
    _scoped_tables_cache = None
