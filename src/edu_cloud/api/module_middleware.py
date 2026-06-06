"""
Module check middleware: blocks API requests for disabled modules.

Route prefix -> module_code mapping. Requests to disabled modules get 403.
Key design decisions (F-02/F-03/F-04 fixes):
- JWT does NOT contain school_id. We extract active_role_id from JWT,
  then query UserRole to get school_id.
- Platform admins without a school-scoped role skip module checks.
- Uses decode_token (shared/auth.py) and async_session (database.py).
"""
import logging

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse
from sqlalchemy import select

from edu_cloud.models.school_settings import SchoolModule

logger = logging.getLogger(__name__)

# Route prefix -> module_code mapping
ROUTE_MODULE_MAP = {
    "/api/v1/exams": "exam",
    "/api/v1/subjects": "exam",
    "/api/v1/questions": "exam",
    "/api/v1/scan": "exam",
    "/api/v1/card": "exam",
    "/api/v1/templates": "exam",
    "/api/v1/grading": "grading",
    "/api/v1/marking": "grading",
    "/api/v1/analytics": "study_analytics",
    "/api/v1/profile": "study_analytics",
    "/api/v1/knowledge": "research",
    "/api/v1/calendar": "calendar",
    "/api/v1/studio": "studio",
    "/api/v1/homework": "homework",
    "/api/v1/pipeline": "exam",
    "/api/v1/knowledge-tree": "research",
    "/api/v1/bank": "research",
}

# Paths that are never blocked (core infrastructure + base info)
EXEMPT_PREFIXES = (
    "/api/v1/auth",
    "/api/v1/health",
    "/api/v1/version",
    "/api/v1/schools",
    "/api/v1/dashboard",
    "/api/v1/ai",
    "/api/v1/classes",
    "/api/v1/students",
    "/api/v1/joint-exams",
    "/api/v1/notifications",
    "/api/v1/llm-config",
    "/api/v1/workspace",
    "/docs",
    "/openapi.json",
)


def _longest_prefix_match(path: str, route_map: dict) -> str | None:
    """Return the module_code of the LONGEST matching prefix, or None.

    Phase 0.7B item3 (R5-DC2): aligns with the guard
    ``check_module_semantics._actual_gating`` which iterates
    ``sorted(route_map, key=len, reverse=True)``. The previous dict
    insertion-order first-match could resolve an overlapping prefix
    (e.g. ``/api/v1/knowledge`` before ``/api/v1/knowledge-tree``) to a
    different module than the guard models, producing a silent runtime drift.
    """
    for prefix in sorted(route_map, key=len, reverse=True):
        if path.startswith(prefix):
            return route_map[prefix]
    return None


def resolve_module_code(path: str) -> str | None:
    """Decide the module_code to gate ``path`` on, or None to pass through.

    Mirrors the guard's decision algorithm exactly: exempt prefixes first
    (never gated), then longest-prefix gated match. Exempt and gated prefix
    sets are disjoint, so the exempt-first ordering is behaviourally inert
    today and only locks the two algorithms together against future overlap.
    """
    if any(path.startswith(p) for p in EXEMPT_PREFIXES):
        return None
    return _longest_prefix_match(path, ROUTE_MODULE_MAP)


class ModuleCheckMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        path = request.url.path

        # Resolve module via the shared guard-aligned decision (exempt-first,
        # then longest-prefix gated). None => exempt or unmapped => pass through.
        module_code = resolve_module_code(path)
        if module_code is None:
            return await call_next(request)

        # Extract active_role_id from JWT to resolve school_id
        auth_header = request.headers.get("authorization", "")
        if not auth_header.startswith("Bearer "):
            return await call_next(request)

        try:
            from edu_cloud.shared.auth import decode_token
            payload = decode_token(auth_header.split(" ")[1])
            active_role_id = payload.get("active_role_id")
        except Exception as e:
            logger.debug("module_middleware: JWT decode failed for %s: %s", path, e)
            return await call_next(request)

        from edu_cloud.database import async_session

        if not active_role_id:
            # Impersonation tokens have effective_school_id instead
            school_id = payload.get("effective_school_id") if payload.get("is_impersonation") else None
            if not school_id:
                return await call_next(request)
        else:
            # Query UserRole to get school_id
            from edu_cloud.models.user_role import UserRole

            school_id = None
            async with async_session() as db:
                result = await db.execute(
                    select(UserRole.school_id).where(UserRole.id == active_role_id)
                )
                row = result.first()
                if row:
                    school_id = row[0]

        if not school_id:
            return await call_next(request)

        # Check module status
        async with async_session() as db:
            result = await db.execute(
                select(SchoolModule.enabled).where(
                    SchoolModule.school_id == school_id,
                    SchoolModule.module_code == module_code,
                )
            )
            row = result.first()

        # If module exists and is disabled -> block
        if row is not None and not row[0]:
            return JSONResponse(
                status_code=403,
                content={"detail": f"模块「{module_code}」未启用"},
            )

        return await call_next(request)
