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
from edu_cloud.logging_config import request_id_var, current_user_var, setup_logging

_BOOT_TIME = datetime.now(timezone(timedelta(hours=8))).strftime("%Y-%m-%d %H:%M:%S")

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
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
    import edu_cloud.modules.knowledge.models  # noqa: F401 — KnowledgePoint/QuestionKnowledgePoint
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

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    logger.info("database tables created")

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

    app = FastAPI(title="edu-cloud", version="0.1.0", lifespan=lifespan)

    # CORS — must be added before other middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.CORS_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

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
        token = request_id_var.set(req_id)

        # Best-effort: extract user_id from JWT for audit logging
        user_token = None
        auth_header = request.headers.get("authorization", "")
        if auth_header.startswith("Bearer "):
            try:
                from edu_cloud.shared.auth import decode_token
                payload = decode_token(auth_header[7:])
                uid = payload.get("sub")
                if uid:
                    user_token = current_user_var.set(uid)
            except Exception:
                logger.debug("request log: token decode skipped")

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
            if user_token:
                current_user_var.reset(user_token)

    # Register routers — auth stays in api/
    from edu_cloud.api.auth import router as auth_router
    app.include_router(auth_router)

    # Dashboard summary (role-scoped aggregation)
    from edu_cloud.api.dashboard import router as dashboard_router
    app.include_router(dashboard_router)

    # AI agent stays in api/ (Batch 4)
    from edu_cloud.api.ai import router as ai_router
    app.include_router(ai_router)

    # exam-ai compat layer (paper-seg zero-change integration)
    from edu_cloud.api.compat_router import router as compat_router
    app.include_router(compat_router)

    # All module routers
    from edu_cloud.modules.school.router import router as schools_router
    from edu_cloud.modules.exam.router import router as exam_router
    from edu_cloud.modules.exam.router import question_router
    from edu_cloud.modules.exam.joint_exam_router import router as joint_exams_router
    from edu_cloud.modules.exam.results_router import router as results_router
    from edu_cloud.modules.exam.workspace_router import router as workspace_router
    from edu_cloud.modules.exam.llm_config_router import router as llm_config_router
    from edu_cloud.modules.student.router import router as student_router
    from edu_cloud.modules.student.teacher_router import router as teacher_router
    from edu_cloud.modules.card.router import router as card_router
    from edu_cloud.modules.card.template_router import router as template_router
    from edu_cloud.modules.scan.router import router as scan_router
    from edu_cloud.modules.grading.router import router as grading_router
    from edu_cloud.modules.grading.assignment_router import router as grading_assignment_router
    from edu_cloud.modules.grading.quality_router import router as quality_router
    from edu_cloud.modules.marking.router import router as marking_router
    from edu_cloud.modules.analytics.router import router as analytics_router
    from edu_cloud.modules.knowledge.router import router as knowledge_router
    from edu_cloud.modules.pipeline.router import router as pipeline_router
    from edu_cloud.modules.studio.router import router as studio_router
    from edu_cloud.modules.calendar.router import router as calendar_router
    from edu_cloud.api.notifications_api import router as notifications_router
    from edu_cloud.modules.school.settings_router import router as settings_router
    from edu_cloud.modules.school.assignment_router import router as assignment_router
    from edu_cloud.modules.school.selection_router import router as selection_router
    from edu_cloud.modules.school.capability_router import router as capability_router
    from edu_cloud.modules.school.audit_router import router as audit_router
    from edu_cloud.modules.homework.router import router as homework_router
    from edu_cloud.modules.profile.router import router as profile_router
    from edu_cloud.modules.bank.router import router as bank_router
    from edu_cloud.modules.knowledge_tree.router import router as knowledge_tree_router
    from edu_cloud.modules.scan.pipeline_router import router as scan_pipeline_router
    from edu_cloud.modules.conduct.parent_router import router as conduct_parent_router
    from edu_cloud.modules.conduct.admin_router import router as conduct_admin_router
    from edu_cloud.modules.menu.router import router as menu_router
    from edu_cloud.modules.academic.router import router as academic_router
    for r in [schools_router, settings_router, assignment_router, selection_router, capability_router, audit_router, homework_router, exam_router, question_router, joint_exams_router,
              results_router, workspace_router, llm_config_router, student_router,
              card_router, template_router, scan_router, grading_router,
              marking_router, analytics_router, knowledge_router, pipeline_router,
              studio_router, calendar_router, notifications_router,
              grading_assignment_router, quality_router, profile_router, bank_router,
              knowledge_tree_router, scan_pipeline_router,
              conduct_parent_router, conduct_admin_router, menu_router,
              teacher_router, academic_router]:
        app.include_router(r)

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
        return {"version": "0.1.0", "boot_time": _BOOT_TIME}

    return app
