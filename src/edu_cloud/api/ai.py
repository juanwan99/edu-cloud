"""AI Agent API — chat SSE + sessions CRUD + health。"""
import asyncio
import json
import logging
import uuid
from dataclasses import dataclass

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from edu_cloud.database import get_db
from edu_cloud.api.deps import require_permission, get_current_user
from edu_cloud.core.permissions import Permission
from edu_cloud.ai.registry import tools
from edu_cloud.ai.audit import AuditLogger
from edu_cloud.ai.anonymizer import Anonymizer
from edu_cloud.ai.tool_access import ToolAccessResolver
from edu_cloud.ai.tool_context import ToolContext
from edu_cloud.ai.llm_adapter import LLMProxyAdapter
from edu_cloud.ai.capability_probe import CapabilityProbe, LoopStrategy
from edu_cloud.ai.sensitivity_router import SensitivityRouter
from edu_cloud.ai.prompts import build_teacher_prompt
from edu_cloud.services.agent_profile_service import AgentProfileService
from edu_cloud.services.school_settings_service import get_enabled_modules
from edu_cloud.services.capability_service import get_capabilities
from edu_cloud.config import settings
import edu_cloud.ai.tools  # noqa: F401 — trigger tool registration
from edu_cloud.ai.supervisor import Supervisor
from edu_cloud.ai.agent_team import teams as team_registry
from edu_cloud.ai.memory_store import MemoryStore
from edu_cloud.ai.memory_injector import MemoryInjector
from edu_cloud.ai.memory_extractor import MemoryExtractor
import edu_cloud.ai.teams  # noqa: F401 — trigger team registration
from edu_cloud.ai.runtime import AgentRuntime, AgentContext
from edu_cloud.modules.exam.slot_selector import resolve_agent_slots

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1/ai", tags=["ai"])


# ── Session state (in-memory, per-process) ──────────────────────────────
@dataclass
class _SessionState:
    anonymizer: Anonymizer
    owner_id: str = ""
    history: list = None  # list[Message] — multi-turn conversation history
    last_access: float = 0.0  # time.time() epoch

    def __post_init__(self):
        if self.history is None:
            self.history = []
        if not self.last_access:
            import time
            self.last_access = time.time()

    def touch(self):
        import time
        self.last_access = time.time()


_sessions: dict[str, _SessionState] = {}
_sessions_lock = asyncio.Lock()


async def _purge_expired_sessions():
    """Remove sessions older than AI_SESSION_TTL."""
    import time
    ttl = settings.AI_SESSION_TTL
    now = time.time()
    expired = [sid for sid, s in _sessions.items() if now - s.last_access > ttl]
    for sid in expired:
        del _sessions[sid]


# ── Request model ────────────────────────────────────────────────────────
class ChatRequest(BaseModel):
    message: str
    session_id: str | None = None

    @property
    def validated_message(self) -> str:
        msg = self.message.strip()
        if not msg:
            raise ValueError("消息不能为空")
        if len(msg) > 2000:
            raise ValueError("消息长度不能超过 2000 字符")
        return msg


# ── Endpoints ─────────────────────────────────────────────────────────────
@router.get("/health")
async def ai_health():
    tool_count = len(tools.list_tools())
    return {"status": "available", "tools": tool_count}


@router.post("/chat")
async def ai_chat(
    req: ChatRequest,
    current=Depends(require_permission(Permission.USE_AI_CHAT)),
    db: AsyncSession = Depends(get_db),
):
    try:
        message = req.validated_message
    except ValueError as e:
        return {"error": str(e)}

    user = current["user"]
    role_obj = current["current_role"]
    role = role_obj.role if hasattr(role_obj, "role") else "unknown"

    # DataScope computation (best-effort)
    data_scope = None
    try:
        from edu_cloud.ai.data_scope import DataScopeBuilder
        data_scope = await DataScopeBuilder(db).build(user.id, role_id=role_obj.id)
    except Exception as scope_exc:
        logger.warning("DataScope build failed, using manual scope: %s", scope_exc)

    scope = {}
    if hasattr(role_obj, "school_id") and role_obj.school_id:
        scope["school"] = role_obj.school_id
    if hasattr(role_obj, "class_ids") and role_obj.class_ids:
        scope["classes"] = role_obj.class_ids
    if hasattr(role_obj, "grade_ids") and role_obj.grade_ids:
        scope["grades"] = role_obj.grade_ids
    if hasattr(role_obj, "subject_codes") and role_obj.subject_codes:
        scope["subjects"] = role_obj.subject_codes

    # DB audit
    audit = AuditLogger(db)
    session_id = req.session_id or str(uuid.uuid4())

    async with _sessions_lock:
        if session_id not in _sessions:
            try:
                await audit.create_session(user.id, role, context=scope)
            except Exception as e:
                logger.warning("Failed to create audit session: %s", e)

        school_id = getattr(role_obj, "school_id", None)

        # Session state + Anonymizer
        session_state = _sessions.setdefault(
            session_id, _SessionState(anonymizer=Anonymizer(), owner_id=user.id)
        )
        session_state.touch()
        await _purge_expired_sessions()

    # Agent profile + slot resolution (best-effort)
    profile = None
    enabled_modules = None
    capabilities = {}
    user_slots = []
    system_slots = []
    enhanced_enabled = False
    try:
        profile = await AgentProfileService.get_or_create(
            db, user_id=user.id, school_id=school_id or "", display_name=user.display_name,
        )
        enabled_modules = await get_enabled_modules(db, school_id=school_id) if school_id else None
        caps_list = await get_capabilities(db, school_id=school_id, role=role) if school_id else []
        capabilities = {(c.domain, c.action): c.enabled for c in caps_list}

        # Dual-model slot resolution (F003 fix)
        if school_id:
            user_slots, system_slots = await resolve_agent_slots(db, school_id=school_id)
            if system_slots:
                from edu_cloud.models.school_settings import SchoolSetting
                from sqlalchemy import select as sa_select
                setting = (await db.execute(
                    sa_select(SchoolSetting).where(
                        SchoolSetting.school_id == school_id,
                        SchoolSetting.key == "ai_enhanced_enabled",
                    )
                )).scalar_one_or_none()
                enhanced_enabled = setting is not None and setting.value == "true"
    except Exception as setup_exc:
        logger.warning("Agent setup failed: %s", setup_exc)

    # Build AgentContext
    agent_ctx = AgentContext(
        db=db,
        user_id=str(user.id),
        school_id=school_id or "",
        role=role,
        data_scope=data_scope,
        session_id=session_id,
        user_slots=user_slots,
        system_slots=system_slots,
        enhanced_enabled=enhanced_enabled,
        class_ids=getattr(role_obj, "class_ids", None),
        subject_codes=getattr(role_obj, "subject_codes", None),
        capabilities=capabilities,
        enabled_modules=list(enabled_modules) if enabled_modules else [],
        display_name=user.display_name or "",
        school_name=scope.get("school", ""),
        anonymizer=session_state.anonymizer,
    )

    runtime = AgentRuntime()

    async def event_stream():
        try:
            async for event in runtime.run(
                message=message,
                context=agent_ctx,
                history=session_state.history,
            ):
                if event.type == "done":
                    event.data["session_id"] = session_id
                yield f"data: {json.dumps(event.to_dict(), ensure_ascii=False)}\n\n"
        finally:
            # F002: write back history from runtime
            last_history = runtime.get_last_history()
            if last_history is not None:
                session_state.history = last_history
            # F004: use real execution receipt
            run_info = runtime.get_last_run_info() or {}
            if profile is not None:
                try:
                    await AgentProfileService.record_run(
                        db,
                        profile_id=profile.id,
                        session_id=session_id,
                        tools_resolved=run_info.get("tools_resolved", []),
                        tools_selected=[],
                        model_used=run_info.get("model_used", "ai-chat"),
                        model_tier=run_info.get("model_tier", "tier3"),
                        intent_domains=[],
                    )
                    await db.commit()
                except Exception as rec_exc:
                    logger.warning("Failed to record AgentRun: %s", rec_exc)

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={"X-Session-Id": session_id},
    )


@router.get("/sessions")
async def list_sessions(current=Depends(get_current_user)):
    user = current["user"]
    async with _sessions_lock:
        owned = [sid for sid, s in _sessions.items() if s.owner_id == user.id]
    return {"sessions": owned}


@router.delete("/sessions/{session_id}")
async def delete_session(
    session_id: str,
    current=Depends(get_current_user),
):
    user = current["user"]
    async with _sessions_lock:
        state = _sessions.get(session_id)
        if state is None:
            return {"deleted": False, "reason": "session not found"}
        if state.owner_id != user.id:
            raise HTTPException(status_code=403, detail="无权删除他人会话")
        del _sessions[session_id]
    return {"deleted": True}
