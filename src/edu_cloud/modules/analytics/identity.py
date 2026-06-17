"""Backward-compatible re-export of shared student identity resolution.

The canonical implementation now lives in the module-external shared layer
``edu_cloud.services.student_identity`` so that both ``analytics`` and
``pipeline`` can resolve canonical student identity from one source without a
cross-module dependency (D-03B). Existing ``edu_cloud.modules.analytics.identity``
import sites keep working through this shim.
"""
from __future__ import annotations

from edu_cloud.services.student_identity import (  # noqa: F401
    StudentIdentity,
    resolve_student_identities,
)

__all__ = ["StudentIdentity", "resolve_student_identities"]
