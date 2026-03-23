import logging
import time
from contextlib import asynccontextmanager
from datetime import datetime, timezone, timedelta
from uuid import uuid4

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from edu_cloud.config import settings
from edu_cloud.services.exceptions import (
    NotFoundError, PermissionDeniedError, ValidationError as SvcValidationError,
    ConflictError, StateError,
)
from edu_cloud.logging_config import request_id_var, setup_logging

_BOOT_TIME = datetime.now(timezone(timedelta(hours=8))).strftime("%Y-%m-%d %H:%M:%S")

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Dev: create tables + seed platform admin
    from edu_cloud.database import engine
    from edu_cloud.models.base import Base
    import edu_cloud.models.school  # noqa: F401
    import edu_cloud.modules.exam.models  # noqa: F401
    import edu_cloud.models.user  # noqa: F401
    import edu_cloud.models.user_role  # noqa: F401
    import edu_cloud.models.student  # noqa: F401
    import edu_cloud.models.class_group  # noqa: F401
    import edu_cloud.models.exam  # noqa: F401 — stub re-exports from modules.exam.models
    import edu_cloud.models.ai_session  # noqa: F401
    import edu_cloud.models.document  # noqa: F401
    import edu_cloud.models.approval  # noqa: F401
    import edu_cloud.models.calendar  # noqa: F401
    import edu_cloud.models.notification  # noqa: F401
    import edu_cloud.core.models.llm_slot  # noqa: F401

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    logger.info("database tables created")

    # Load knowledge base if enabled
    from edu_cloud.knowledge.store import knowledge_store
    if settings.KNOWLEDGE_ENABLED:
        try:
            knowledge_store.load(settings.KNOWLEDGE_BASE_DIR)
        except Exception as e:
            logger.warning(f"Knowledge base loading failed (non-fatal): {e}")

    # Seed platform admin (new User + UserRole model)
    from edu_cloud.database import async_session
    from edu_cloud.models.user import User
    from edu_cloud.models.user_role import UserRole
    from sqlalchemy import select

    async with async_session() as db:
        existing = (
            await db.execute(select(User).where(User.username == "admin"))
        ).scalar_one_or_none()
        if not existing:
            admin = User(
                username="admin",
                display_name="平台管理员",
            )
            admin.set_password("123456")
            db.add(admin)
            await db.flush()
            db.add(UserRole(
                user_id=admin.id,
                role="platform_admin",
                is_primary=True,
            ))
            await db.commit()
            logger.info("seed: platform admin created (admin/123456)")
        else:
            logger.debug("seed: platform admin already exists, skipping")

    yield


def create_app() -> FastAPI:
    setup_logging(
        level=getattr(logging, settings.LOG_LEVEL.upper(), logging.DEBUG),
        log_dir=settings.LOG_DIR,
        file_level=getattr(logging, settings.LOG_FILE_LEVEL.upper(), logging.INFO),
    )
    logger.info("edu-cloud starting, boot_time=%s", _BOOT_TIME)

    app = FastAPI(title="edu-cloud", version="0.1.0", lifespan=lifespan)

    # CORS — must be added before other middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.CORS_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Global exception handlers — map Service exceptions to HTTP status codes
    @app.exception_handler(NotFoundError)
    async def not_found_handler(request, exc):
        return JSONResponse(status_code=404, content={"detail": str(exc)})

    @app.exception_handler(PermissionDeniedError)
    async def permission_denied_handler(request, exc):
        return JSONResponse(status_code=403, content={"detail": str(exc)})

    @app.exception_handler(SvcValidationError)
    async def validation_handler(request, exc):
        return JSONResponse(status_code=422, content={"detail": str(exc)})

    @app.exception_handler(ConflictError)
    async def conflict_handler(request, exc):
        return JSONResponse(status_code=409, content={"detail": str(exc)})

    @app.exception_handler(StateError)
    async def state_error_handler(request, exc):
        return JSONResponse(status_code=409, content={"detail": str(exc)})

    @app.middleware("http")
    async def request_logging(request: Request, call_next):
        req_id = request.headers.get("X-Request-ID") or uuid4().hex[:12]
        token = request_id_var.set(req_id)

        start = time.perf_counter()
        try:
            response = await call_next(request)
            ms = (time.perf_counter() - start) * 1000
            path = request.url.path
            if not path.startswith(("/docs", "/openapi", "/favicon")):
                log = logger.info if response.status_code < 400 else logger.warning
                log("%s %s → %d (%.0fms)", request.method, path, response.status_code, ms)
            response.headers["X-Request-ID"] = req_id
            return response
        except Exception as exc:
            # Let registered Service exceptions propagate to FastAPI exception_handlers
            if isinstance(exc, (NotFoundError, PermissionDeniedError,
                                SvcValidationError, ConflictError, StateError)):
                raise
            # Truly unknown exceptions → 500
            ms = (time.perf_counter() - start) * 1000
            path = request.url.path
            logger.error("%s %s → 500 (%.0fms) unhandled exception", request.method, path, ms, exc_info=True)
            from starlette.responses import PlainTextResponse
            error_response = PlainTextResponse("Internal Server Error", status_code=500)
            error_response.headers["X-Request-ID"] = req_id
            return error_response
        finally:
            request_id_var.reset(token)

    # Register routers
    from edu_cloud.api.auth import router as auth_router
    from edu_cloud.api.sync import router as sync_router
    from edu_cloud.api.sync_students import router as sync_students_router
    from edu_cloud.api.schools import router as schools_router
    from edu_cloud.api.joint_exams import router as joint_exams_router
    from edu_cloud.api.results import router as results_router
    from edu_cloud.api.workspace import router as workspace_router
    from edu_cloud.api.ai import router as ai_router
    from edu_cloud.api.studio import router as studio_router
    from edu_cloud.api.calendar import router as calendar_router
    app.include_router(auth_router)
    app.include_router(sync_router)
    app.include_router(sync_students_router)
    app.include_router(schools_router)
    app.include_router(joint_exams_router)
    app.include_router(results_router)
    app.include_router(workspace_router)
    app.include_router(ai_router)
    app.include_router(studio_router)
    app.include_router(calendar_router)

    @app.get("/api/v1/health")
    async def health():
        return {"status": "ok", "service": "edu-cloud"}

    @app.get("/api/v1/version")
    async def version():
        return {"version": "0.1.0", "boot_time": _BOOT_TIME}

    return app
