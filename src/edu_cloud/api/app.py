import logging
import os
import subprocess
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
from edu_cloud.logging_config import (
    request_id_var, current_user_var, trace_id_var, current_school_var,
    log_event, setup_logging,
)

_BOOT_TIME = datetime.now(timezone(timedelta(hours=8))).strftime("%Y-%m-%d %H:%M:%S")


def _get_repo_root():
    try:
        return subprocess.check_output(
            ['git', 'rev-parse', '--show-toplevel'], text=True
        ).strip()
    except Exception:
        return os.path.dirname(os.path.abspath(__file__))


def _get_git_hash():
    try:
        return subprocess.check_output(
            ['git', 'rev-parse', '--short', 'HEAD'], text=True
        ).strip()
    except Exception:
        return 'unknown'


def _is_source_dirty():
    try:
        subprocess.check_call(
            ['git', 'diff', '--quiet', 'HEAD', '--', 'src/'],
            cwd=_get_repo_root()
        )
        return False
    except Exception:
        return True


_GIT_HASH = _get_git_hash()
_SOURCE_DIRTY = _is_source_dirty()

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    from edu_cloud.startup_checks import run_startup_checks
    await run_startup_checks(settings)

    # Dev: create tables + seed platform admin
    from edu_cloud.database import engine
    from edu_cloud.models.base import Base
    # Core models
    import edu_cloud.models.school  # noqa: F401
    import edu_cloud.models.user  # noqa: F401
    import edu_cloud.models.user_role  # noqa: F401
    import edu_cloud.models.llm_slot  # noqa: F401
    # Module models (canonical locations)
    import edu_cloud.modules.exam.models  # noqa: F401 — Exam/Subject/Question/ExamResult/JointExam*
    import edu_cloud.modules.student.models  # noqa: F401 — Class/Student
    import edu_cloud.modules.card.models  # noqa: F401 — Template/CardSkeleton
    import edu_cloud.modules.scan.models  # noqa: F401 — ScanTask/StudentAnswer
    import edu_cloud.modules.grading.models  # noqa: F401 — Rubric/GradingTask/GradingResult/GradingAssignment/GradingQualityCheck
    import edu_cloud.modules.marking.models  # noqa: F401 — (emptied, merged into grading module)
    import edu_cloud.modules.knowledge.models  # noqa: F401 — QuestionKnowledgePoint
    import edu_cloud.modules.bank.models  # noqa: F401 — BankQuestion/StudentErrorBook
    import edu_cloud.modules.profile.models  # noqa: F401 — StudentExamSnapshot/KnowledgeMastery/ErrorPattern
    import edu_cloud.ai.models  # noqa: F401 — AiSession/AiToolCall
    # Legacy models (re-export stubs, still needed for Document/Approval/Calendar/Notification)
    import edu_cloud.models.document  # noqa: F401
    import edu_cloud.models.approval  # noqa: F401
    import edu_cloud.models.calendar  # noqa: F401
    import edu_cloud.models.notification  # noqa: F401
    import edu_cloud.models.school_settings  # noqa: F401
    import edu_cloud.models.teacher_assignment  # noqa: F401
    import edu_cloud.models.subject_selection  # noqa: F401
    import edu_cloud.models.capability  # noqa: F401
    import edu_cloud.models.audit_log  # noqa: F401
    import edu_cloud.modules.homework.models  # noqa: F401
    # Agent evolution models
    import edu_cloud.models.guardian  # noqa: F401
    import edu_cloud.models.workflow  # noqa: F401
    import edu_cloud.models.agent_finding  # noqa: F401
    import edu_cloud.models.agent_snapshot  # noqa: F401
    import edu_cloud.models.scope_version  # noqa: F401
    import edu_cloud.models.memory  # noqa: F401 — EntityMemory/ProjectState
    import edu_cloud.modules.knowledge_tree.models  # noqa: F401 — ConceptGraphNode/Edge/EditSyncFailure
    import edu_cloud.modules.menu.models  # noqa: F401 — Alembic autogenerate (MenuConfig)
    import edu_cloud.modules.analytics.models  # noqa: F401 — Alembic autogenerate (ClassAnalysis/StudentAnalysis/StudentKnpMastery)
    # ── S1-C admin schema (2026-04-24): design §4.1 deliverables 1.3/1.4 ──
    import edu_cloud.models.grade  # noqa: F401 — Grade
    import edu_cloud.models.teaching_plan  # noqa: F401 — TeachingPlan

    # create_all removed (C-02): use 'alembic upgrade head' for all environments.
    # Test fixtures in conftest.py still use create_all for in-memory SQLite.
    logger.info("database: schema managed by alembic (create_all removed)")

    # Sync knowledge.db → PostgreSQL (idempotent, non-fatal)
    from edu_cloud.database import async_session  # F001: import before use
    try:
        async with async_session() as db:
            from edu_cloud.modules.knowledge_tree.sync_service import sync_knowledge_on_startup
            sync_result = await sync_knowledge_on_startup(db)
            if sync_result["status"] == "synced":
                logger.info(
                    "sync: knowledge.db → PG complete (%d nodes, %d edges, %d DAs, %d KP maps)",
                    sync_result["nodes"], sync_result["edges"], sync_result["das"], sync_result["kp_map"],
                )
    except Exception as e:
        logger.warning("sync: knowledge.db sync failed (non-fatal): %s", e)

    # Load knowledge base if enabled
    from edu_cloud.knowledge.store import knowledge_store
    if settings.KNOWLEDGE_ENABLED:
        try:
            knowledge_store.load(settings.KNOWLEDGE_BASE_DIR)
        except Exception as e:
            logger.error("Knowledge base loading failed (non-fatal): %s", e)

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
            admin.set_password(settings.SEED_DEFAULT_PASSWORD)
            db.add(admin)
            await db.flush()
            db.add(UserRole(
                user_id=admin.id,
                role="platform_admin",
                is_primary=True,
            ))
            await db.commit()
            logger.info("seed: platform admin created (admin/***)")
        else:
            logger.debug("seed: platform admin already exists, skipping")

    # Seed complete school (idempotent)
    async with async_session() as db:
        from edu_cloud.data.seed_school import seed_complete_school
        result = await seed_complete_school(db)
        if result["status"] == "seeded":
            logger.info(
                "seed: school created — %s students, %d teachers, %d classes",
                result["students"], result["teachers"], result["classes"],
            )
        else:
            logger.debug("seed: school already exists, skipping")

    # Seed demo exam data for the school (idempotent)
    async with async_session() as db:
        from edu_cloud.data.seed_demo import seed_demo_data
        demo_result = await seed_demo_data(db, school_code="YCSY2026")
        if demo_result.get("status") == "already_seeded":
            logger.debug("seed: demo data already exists, skipping")
        elif demo_result.get("status") == "error":
            logger.warning("seed: demo data skipped — %s", demo_result.get("message"))
        else:
            logger.info("seed: demo data created — %d answers", demo_result.get("total_answers", 0))

    # Register W1 workflow with EventBus
    from edu_cloud.ai.workflow.triggers import EventTrigger
    from edu_cloud.ai.workflow.w1_post_exam import W1_POST_EXAM
    from edu_cloud.ai.workflow.registry import WorkflowRegistry
    from edu_cloud.ai.workflow.engine import WorkflowExecutor
    from edu_cloud.core.events import event_bus

    workflow_registry = WorkflowRegistry()
    workflow_registry.register(W1_POST_EXAM)

    async def execute_workflow(workflow_name, school_id, trigger_type, trigger_ref):
        wf = workflow_registry.get(workflow_name)
        if wf:
            async with async_session() as db:
                executor = WorkflowExecutor(db)
                await executor.execute(wf, school_id, trigger_type, trigger_ref)

    trigger = EventTrigger(event_bus, executor_func=execute_workflow)
    trigger.register("exam.published", workflow_name="post_exam_analysis")
    logger.info("workflow: W1 post_exam_analysis registered on exam.published")

    yield


def create_app() -> FastAPI:
    setup_logging(
        level=getattr(logging, settings.LOG_LEVEL.upper(), logging.DEBUG),
        log_dir=settings.LOG_DIR,
        file_level=getattr(logging, settings.LOG_FILE_LEVEL.upper(), logging.INFO),
    )
    logger.info("edu-cloud starting, boot_time=%s", _BOOT_TIME)

    _is_prod = settings.ENVIRONMENT == "production"
    app = FastAPI(
        title="edu-cloud",
        version="0.1.0",
        lifespan=lifespan,
        docs_url=None if _is_prod else "/docs",
        redoc_url=None if _is_prod else "/redoc",
    )

    # CORS — must be added before other middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.CORS_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Rate limiting (N-H08 brute-force protection for login endpoints)
    from edu_cloud.core.rate_limit import limiter
    from slowapi import _rate_limit_exceeded_handler
    from slowapi.errors import RateLimitExceeded

    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

    # Module check middleware — hard block for disabled modules
    from edu_cloud.api.module_middleware import ModuleCheckMiddleware
    app.add_middleware(ModuleCheckMiddleware)

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
        trace_id = request.headers.get("X-Trace-ID") or f"tr_{uuid4().hex[:12]}"
        token = request_id_var.set(req_id)
        trace_token = trace_id_var.set(trace_id)

        # Best-effort: extract user_id and school_id from JWT for audit logging
        user_token = None
        school_token = None
        imp_token = None
        auth_header = request.headers.get("authorization", "")
        if auth_header.startswith("Bearer "):
            try:
                from edu_cloud.shared.auth import decode_token
                payload = decode_token(auth_header[7:])
                uid = payload.get("sub")
                if uid:
                    user_token = current_user_var.set(uid)
                school_id = payload.get("school_id") or payload.get("effective_school_id")
                if school_id:
                    school_token = current_school_var.set(str(school_id))
                if payload.get("is_impersonation"):
                    from edu_cloud.logging_config import impersonator_var
                    imp_token = impersonator_var.set(payload.get("impersonator_id"))
            except Exception:
                logger.debug("request log: token decode skipped")

        start = time.perf_counter()
        path = request.url.path
        try:
            response = await call_next(request)
            ms = (time.perf_counter() - start) * 1000
            if not path.startswith(("/docs", "/openapi", "/favicon", "/api/v1/client-logs")):
                log = logger.info if response.status_code < 400 else logger.warning
                log("%s %s → %d (%.0fms)", request.method, path, response.status_code, ms)
                # Slow request alert
                if ms > 1000:
                    log_event(
                        "edu_cloud.api", logging.WARNING, "alert",
                        "http.slow_request",
                        f"Slow request: {request.method} {path} took {ms:.0f}ms",
                        duration_ms=ms,
                        method=request.method, path=path,
                        status_code=response.status_code,
                    )
            response.headers["X-Request-ID"] = req_id
            response.headers["X-Trace-ID"] = trace_id
            response.headers["X-Content-Type-Options"] = "nosniff"
            response.headers["X-Frame-Options"] = "DENY"
            response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
            return response
        except Exception as exc:
            # Let registered Service exceptions propagate to FastAPI exception_handlers
            if isinstance(exc, (NotFoundError, PermissionDeniedError,
                                SvcValidationError, ConflictError, StateError)):
                raise
            # Truly unknown exceptions → 500
            ms = (time.perf_counter() - start) * 1000
            logger.error("%s %s → 500 (%.0fms) unhandled exception", request.method, path, ms, exc_info=True)
            from starlette.responses import PlainTextResponse
            error_response = PlainTextResponse("Internal Server Error", status_code=500)
            error_response.headers["X-Request-ID"] = req_id
            error_response.headers["X-Trace-ID"] = trace_id
            return error_response
        finally:
            request_id_var.reset(token)
            trace_id_var.reset(trace_token)
            if user_token:
                current_user_var.reset(user_token)
            if school_token:
                current_school_var.reset(school_token)
            if imp_token:
                from edu_cloud.logging_config import impersonator_var
                impersonator_var.reset(imp_token)
            # Clear tenant context to prevent leaking across requests
            from edu_cloud.core.tenant_registry import clear_tenant
            clear_tenant()

    # ── Route registration (all routers from registry) ──
    from edu_cloud.api.router_registry import register_all
    register_all(app)

    from pathlib import Path
    from starlette.staticfiles import StaticFiles
    upload_dir = Path(settings.UPLOAD_DIR).resolve()
    upload_dir.mkdir(parents=True, exist_ok=True)
    app.mount("/uploads", StaticFiles(directory=str(upload_dir)), name="uploads")

    @app.get("/api/v1/health")
    async def health():
        return {"status": "ok", "service": "edu-cloud"}

    @app.get("/api/v1/version")
    async def version():
        return {
            "version": "0.1.0",
            "boot_time": _BOOT_TIME,
            "git_hash": _GIT_HASH,
            "source_dirty": _SOURCE_DIRTY,
            "pid": os.getpid(),
        }

    return app
