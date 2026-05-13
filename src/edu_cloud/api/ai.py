"""AI Agent API — Pydantic AI engine (replaces old AgentLoop/Supervisor pipeline).

Endpoints:
  GET  /api/v1/ai/health               — tool count + status
  GET  /api/v1/ai/ref-types             — reference type definitions
  GET  /api/v1/ai/refs                  — reference resolver
  POST /api/v1/ai/chat                  — SSE chat (EduAgentRuntime)
  POST /api/v1/ai/runs/{run_id}/confirmations/{confirmation_id}  — write approval
  GET  /api/v1/ai/sessions              — list sessions
  DELETE /api/v1/ai/sessions/{id}       — delete session
"""
import asyncio
import json
import logging
import time
import uuid
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from edu_cloud.core.auth import get_current_user, require_permission
from edu_cloud.core.permissions import Permission
from edu_cloud.database import async_session, get_db

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1/ai", tags=["ai"])


# ── Session state (in-memory, per-process) ──────────────────────────────

class _SessionState:
    __slots__ = ("anonymizer", "owner_id", "history", "last_access", "runtime", "run_lock")

    def __init__(self, *, anonymizer, owner_id: str = ""):
        self.anonymizer = anonymizer
        self.owner_id = owner_id
        self.history: list = []
        self.last_access: float = time.time()
        self.runtime = None
        self.run_lock = asyncio.Lock()

    def touch(self):
        self.last_access = time.time()


_sessions: dict[str, _SessionState] = {}
_sessions_lock = asyncio.Lock()


async def _purge_expired_sessions():
    from edu_cloud.config import settings
    ttl = settings.AI_SESSION_TTL
    now = time.time()
    expired = [sid for sid, s in _sessions.items() if now - s.last_access > ttl]
    for sid in expired:
        del _sessions[sid]


# ── Request / Response models ───────────────────────────────────────────

class ChatRequest(BaseModel):
    message: str
    session_id: str | None = None
    refs: list[dict] | None = None

    @property
    def validated_message(self) -> str:
        msg = self.message.strip()
        if not msg:
            raise ValueError("消息不能为空")
        if len(msg) > 2000:
            raise ValueError("消息长度不能超过 2000 字符")
        return msg


class ConfirmationRequest(BaseModel):
    decision: Literal["approve", "reject"]
    idempotency_key: str | None = None
    comment: str | None = None


# ── Endpoints ────────────────────────────────────────────────────────────

@router.get("/health")
async def ai_health():
    from edu_cloud.ai.engine.tools import collect_all_tools
    all_tools = collect_all_tools()
    return {"status": "available", "tools": len(all_tools)}


@router.get("/ref-types")
async def ai_ref_types(current=Depends(get_current_user)):
    from edu_cloud.ai.ref_types import REF_TYPES
    return [t.to_dict() for t in REF_TYPES]


@router.get("/refs")
async def ai_refs(
    type: str,
    search: str | None = None,
    parent_id: str | None = None,
    limit: int = 20,
    current=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    from edu_cloud.ai.ref_resolvers import RESOLVERS
    resolver = RESOLVERS.get(type)
    if not resolver:
        raise HTTPException(400, f"Unknown ref type: {type}")

    role_obj = current["current_role"]
    school_id = getattr(role_obj, "school_id", None) or ""
    items = await resolver(db, school_id, search, parent_id, min(limit, 50))
    return {"items": [item.to_dict() for item in items], "total": len(items)}


@router.post("/chat")
async def ai_chat(
    req: ChatRequest,
    current=Depends(require_permission(Permission.USE_AI_CHAT)),
    db: AsyncSession = Depends(get_db),
):
    try:
        message = req.validated_message
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))

    if req.refs:
        ref_lines = [
            f"[引用数据: {r.get('label', '')}（{r.get('type', '')}_id={r.get('id', '')}）]"
            for r in req.refs if r.get("id")
        ]
        if ref_lines:
            message = "\n".join(ref_lines) + "\n\n" + message

    user = current["user"]
    role_obj = current["current_role"]
    role = role_obj.role if hasattr(role_obj, "role") else "unknown"
    school_id = getattr(role_obj, "school_id", None)
    session_id = req.session_id or str(uuid.uuid4())

    # ── Daily request limit (soft, experience-level throttle) ──
    try:
        from datetime import datetime, timezone, timedelta
        from sqlalchemy import func, select as sa_select
        from edu_cloud.models.ai_engine import AiAgentTrace

        tz_utc8 = timezone(timedelta(hours=8))
        today_start_utc8 = datetime.now(tz_utc8).replace(hour=0, minute=0, second=0, microsecond=0)
        today_start_utc = today_start_utc8.astimezone(timezone.utc)

        import hashlib
        user_hash = hashlib.sha256(str(user.id).encode()).hexdigest()[:12]
        daily_count_result = await db.execute(
            sa_select(func.count()).where(
                AiAgentTrace.user_id == user_hash,
                AiAgentTrace.created_at >= today_start_utc,
            )
        )
        daily_count = daily_count_result.scalar() or 0

        daily_limit = 100
        if school_id:
            from edu_cloud.models.school_settings import SchoolSetting
            limit_row = (await db.execute(
                sa_select(SchoolSetting.value).where(
                    SchoolSetting.school_id == school_id,
                    SchoolSetting.key == "ai_daily_chat_limit",
                )
            )).scalar_one_or_none()
            if limit_row:
                daily_limit = int(limit_row)

        if daily_count >= daily_limit:
            raise HTTPException(status_code=429, detail=f"今日 AI 对话次数已达上限（{daily_limit}次）")
    except HTTPException:
        raise
    except Exception as limit_exc:
        logger.warning("Daily limit check failed: %s", limit_exc)

    # ── Session management ──
    async with _sessions_lock:
        from edu_cloud.ai.anonymizer import Anonymizer
        existing = _sessions.get(session_id)
        if existing and existing.owner_id != str(user.id):
            raise HTTPException(403, "Session belongs to another user")

        session_state = _sessions.setdefault(
            session_id, _SessionState(anonymizer=Anonymizer(), owner_id=str(user.id)),
        )
        session_state.touch()
        await _purge_expired_sessions()

    # ── Build DataScope (best-effort) ──
    data_scope = None
    try:
        from edu_cloud.ai.data_scope import DataScopeBuilder
        data_scope = await DataScopeBuilder(db).build(user.id, role_id=role_obj.id)
    except Exception as scope_exc:
        logger.warning("DataScope build failed: %s", scope_exc)

    if data_scope is None:
        from edu_cloud.ai.data_scope import DataScope
        data_scope = DataScope(
            user_id=str(user.id),
            school_id=school_id or "",
            role=role,
            visible_class_ids=getattr(role_obj, "class_ids", None),
            visible_subject_codes=getattr(role_obj, "subject_codes", None),
            visible_grade_ids=getattr(role_obj, "grade_ids", None),
            visible_student_ids=None,
            district_ids=None,
            can_write=False,
            can_see_rankings=role != "parent",
            can_cross_school=role in ("platform_admin", "district_admin"),
            persona="teacher_assistant",
            version=1,
        )

    # ── Load school config ──
    enabled_modules: frozenset[str] = frozenset()
    capabilities: dict[tuple[str, str], bool] = {}
    try:
        from edu_cloud.services.school_settings_service import get_enabled_modules as _get_modules
        from edu_cloud.services.capability_service import get_capabilities
        if school_id:
            mods = await _get_modules(db, school_id=school_id)
            enabled_modules = frozenset(mods) if mods else frozenset()
            caps_list = await get_capabilities(db, school_id=school_id, role=role)
            capabilities = {(c.domain, c.action): c.enabled for c in caps_list}
    except Exception as cfg_exc:
        logger.warning("School config load failed: %s", cfg_exc)

    # ── Collect and filter tools ──
    from edu_cloud.ai.engine.tools import collect_all_tools, filter_tools_for_role
    from edu_cloud.ai.engine.tool_wrapper import TOOL_META_REGISTRY
    all_tools = collect_all_tools()
    allowed_tools = filter_tools_for_role(
        all_tools, role=role, enabled_modules=enabled_modules,
        capabilities=capabilities or None,
    )
    tool_names = [getattr(fn, "_edu_meta", None).name for fn in allowed_tools if getattr(fn, "_edu_meta", None)]

    # ── Build system prompt (with memory) ──
    from edu_cloud.ai.prompts import build_teacher_prompt
    from edu_cloud.ai.memory_store import MemoryStore

    memory_store = MemoryStore()
    memory_context = ""
    try:
        from edu_cloud.ai.memory_injector import MemoryInjector
        injector = MemoryInjector(store=memory_store)
        memory_context = await injector.build_context(
            db, school_id=school_id or "", user_id=str(user.id), role=role,
        )
    except Exception as mem_exc:
        logger.warning("Memory injection failed: %s", mem_exc)

    memories = [line for line in memory_context.split("\n") if line.strip()] if memory_context else None

    system_prompt = build_teacher_prompt(
        role=role,
        display_name=user.display_name or "",
        school_name=str(school_id or ""),
        tool_names=tool_names,
        tier=3,
        memories=memories,
    )

    # ── Agent profile recording (best-effort) ──
    profile = None
    try:
        from edu_cloud.services.agent_profile_service import AgentProfileService
        profile = await AgentProfileService.get_or_create(
            db, user_id=user.id, school_id=school_id or "", display_name=user.display_name,
        )
    except Exception as profile_exc:
        logger.warning("AgentProfile load failed: %s", profile_exc)

    # ── Build EduAgentRuntime ──
    from edu_cloud.ai.engine.edu_runtime import EduAgentRuntime

    runtime = EduAgentRuntime(
        db_sessionmaker=async_session,
        user_id=str(user.id),
        school_id=str(school_id or ""),
        role=role,
        data_scope=data_scope,
        enabled_modules=enabled_modules,
        capabilities=capabilities,
        anonymizer=session_state.anonymizer,
        memory=memory_store,
        session_id=session_id,
        system_prompt=system_prompt,
        tool_meta_registry=TOOL_META_REGISTRY,
        tool_functions=allowed_tools,
    )
    runtime.build_agent()

    session_state.runtime = runtime

    async def event_stream():
        if session_state.run_lock.locked():
            yield f"data: {json.dumps({'type': 'error', 'data': {'message': '该会话正在处理中，请稍后重试'}}, ensure_ascii=False)}\n\n"
            return
        async with session_state.run_lock:
            try:
                async for event in runtime.run(
                    message, message_history=session_state.history,
                ):
                    if event.type == "done":
                        event.data["session_id"] = session_id
                    yield f"data: {json.dumps(event.to_dict(), ensure_ascii=False)}\n\n"
            finally:
                session_state.history = runtime.last_messages
            if profile is not None:
                try:
                    from edu_cloud.services.agent_profile_service import AgentProfileService
                    await AgentProfileService.record_run(
                        db,
                        profile_id=profile.id,
                        session_id=session_id,
                        tools_resolved=tool_names,
                        tools_selected=[],
                        model_used="ai-chat",
                        model_tier="pydantic-ai",
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


@router.post("/runs/{run_id}/confirmations/{confirmation_id}")
async def confirm_tool(
    run_id: str,
    confirmation_id: str,
    req: ConfirmationRequest,
    current=Depends(require_permission(Permission.USE_AI_CHAT)),
):
    """Approve or reject a deferred write tool execution."""
    user = current["user"]

    async with _sessions_lock:
        await _purge_expired_sessions()
        target_session = None
        for _sid, state in _sessions.items():
            rt = state.runtime
            if rt is not None and rt.run_id == run_id and state.owner_id == str(user.id):
                target_session = state
                break

    if target_session is None:
        raise HTTPException(404, "Run not found or expired")

    runtime = target_session.runtime
    if runtime.deps.confirmations.is_expired(confirmation_id):
        raise HTTPException(410, "确认已超时（5 分钟），操作未执行")

    if req.decision == "approve":
        approved_ids = [confirmation_id]
        denied_ids = []
    else:
        approved_ids = []
        denied_ids = [confirmation_id]

    async def confirm_stream():
        try:
            async for event in runtime.resume_after_confirmation(
                approved_ids=approved_ids,
                denied_ids=denied_ids,
            ):
                yield f"data: {json.dumps(event.to_dict(), ensure_ascii=False)}\n\n"
        finally:
            target_session.history = runtime.last_messages

    return StreamingResponse(
        confirm_stream(),
        media_type="text/event-stream",
    )


@router.get("/sessions")
async def list_sessions(current=Depends(get_current_user)):
    user = current["user"]
    async with _sessions_lock:
        owned = [sid for sid, s in _sessions.items() if s.owner_id == str(user.id)]
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
        if state.owner_id != str(user.id):
            raise HTTPException(status_code=403, detail="无权删除他人会话")
        del _sessions[session_id]
    return {"deleted": True}
