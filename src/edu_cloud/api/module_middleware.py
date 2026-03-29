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
    "/api/v1/knowledge": "research",
    "/api/v1/calendar": "calendar",
    "/api/v1/studio": "studio",
    "/api/v1/pipeline": "exam",
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


class ModuleCheckMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        path = request.url.path

        # Skip exempt paths
        if any(path.startswith(p) for p in EXEMPT_PREFIXES):
            return await call_next(request)

        # Find matching module
        module_code = None
        for prefix, code in ROUTE_MODULE_MAP.items():
            if path.startswith(prefix):
                module_code = code
                break

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
        except Exception:
            return await call_next(request)

        if not active_role_id:
            return await call_next(request)

        # Query UserRole to get school_id
        from edu_cloud.database import async_session
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
