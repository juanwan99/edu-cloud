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
    # Phase 0.7B item4: 收口后端 fail-open drift（参照 0.6C profile）。前端 /conduct、/exam-import
    # 已标 moduleCode（authGuard 已 fail-close 导航），后端补同源门控 = 模块关闭即功能不可用。
    "/api/v1/conduct": "conduct",
    "/api/v1/exam-imports": "exam",
    # Phase 0.7D: 收口 academic 后端 fail-open（双面 fail-open 最后一处）。前端 /academic/* 已配套
    # 接 teaching 门控（routeAccess/router-meta/sidebar，authGuard 已 fail-close 导航），后端补同源
    # defense-in-depth。teaching 默认未开启（不在 DEFAULT_ENABLED），但中间件仅在 SchoolModule(teaching)
    # 行存在且 enabled=False 时 403；未配置行 → pass-through，前端入口亦隐藏，双面对齐。
    "/api/v1/academic": "teaching",
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
    # Phase 0.7B item5: 收口 hygiene drift——这些入口本就 pass-through（不在 MAP），显式入 exempt
    # 令豁免意图可见（行为零变更）。menus/portal/grades/teachers 为跨模块基础信息，client-logs 为前端日志回传。
    "/api/v1/menus",
    "/api/v1/portal",
    "/api/v1/grades",
    "/api/v1/teachers",
    "/api/v1/client-logs",
    "/docs",
    "/openapi.json",
)


def _prefix_matches(path: str, prefix: str) -> bool:
    """True iff ``prefix`` matches ``path`` at a path-segment boundary.

    Phase 0.7B item3 hardening (codex-review R2 F-001): bare ``startswith`` is a
    character prefix, not a segment boundary — ``/api/v1/conductors`` would match
    ``/api/v1/conduct`` and get wrongly gated to the conduct module. A prefix
    matches only when the path equals it or continues with ``/`` (a sub-path).
    """
    return path == prefix or path.startswith(prefix + "/")


def _longest_prefix_match(path: str, route_map: dict) -> str | None:
    """Return the module_code of the LONGEST matching prefix, or None.

    Phase 0.7B item3 (R5-DC2): aligns with the guard
    ``check_module_semantics._actual_gating`` which iterates
    ``sorted(route_map, key=len, reverse=True)``. The previous dict
    insertion-order first-match could resolve an overlapping prefix
    (e.g. ``/api/v1/knowledge`` before ``/api/v1/knowledge-tree``) to a
    different module than the guard models, producing a silent runtime drift.
    Matching is segment-boundary safe (see ``_prefix_matches``).
    """
    for prefix in sorted(route_map, key=len, reverse=True):
        if _prefix_matches(path, prefix):
            return route_map[prefix]
    return None


def resolve_module_code(path: str) -> str | None:
    """Decide the module_code to gate ``path`` on, or None to pass through.

    Mirrors the guard's decision algorithm exactly: exempt prefixes first
    (never gated), then longest-prefix gated match. Exempt and gated prefix
    sets are disjoint, so the exempt-first ordering is behaviourally inert
    today and only locks the two algorithms together against future overlap.
    """
    if any(_prefix_matches(path, p) for p in EXEMPT_PREFIXES):
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
