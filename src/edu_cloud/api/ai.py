"""AI Agent API — chat SSE + sessions CRUD + health。"""
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
from edu_cloud.ai.agent import Agent
from edu_cloud.ai.llm import LLMChatClient
from edu_cloud.ai.registry import tools
from edu_cloud.ai.audit import AuditLogger
from edu_cloud.ai.context import AgentContext, build_system_prompt
from edu_cloud.ai.anonymizer import Anonymizer
from edu_cloud.ai.tool_access import ToolAccessResolver
from edu_cloud.ai.intent_resolver import IntentResolver
from edu_cloud.ai.model_router import ModelRouter
from edu_cloud.ai.llm_factory import create_llm_for_tier
from edu_cloud.services.agent_profile_service import AgentProfileService
from edu_cloud.services.school_settings_service import get_enabled_modules
from edu_cloud.services.capability_service import get_capabilities
from edu_cloud.config import settings
import edu_cloud.ai.tools  # noqa: F401 — trigger tool registration

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1/ai", tags=["ai"])


# ── Session state (in-memory, per-process) ──────────────────────────────
@dataclass
class _SessionState:
    context: AgentContext
    anonymizer: Anonymizer


_sessions: dict[str, _SessionState] = {}


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

    # Create audit session for new conversations
    if session_id not in _sessions:
        try:
            await audit.create_session(user.id, role, context=scope)
        except Exception as e:
            logger.warning("Failed to create audit session: %s", e)

    school_id = getattr(role_obj, "school_id", None)

    # === Agent Pipeline ===
    try:
        # 1. Agent 身份
        profile = await AgentProfileService.get_or_create(
            db, user_id=user.id, school_id=school_id or "", display_name=user.display_name,
        )

        # 2. 三重权限过滤
        all_specs = tools.get_all_specs()
        enabled_modules = await get_enabled_modules(db, school_id=school_id) if school_id else None
        caps_list = await get_capabilities(db, school_id=school_id, role=role) if school_id else []
        capabilities = {(c.domain, c.action): c.enabled for c in caps_list}

        resolver = ToolAccessResolver()
        available_tools = resolver.resolve(
            all_specs=all_specs, role=role,
            enabled_modules=enabled_modules, capabilities=capabilities,
        )

        # 3. 意图驱动工具裁剪
        intent_resolver = IntentResolver(llm_client=None)  # 规则引擎优先，无 LLM 开销
        selected_tools = await intent_resolver.resolve(message, available_tools)

        # 4. 模型路由
        model_tier = ModelRouter().select(intent_resolver.last_domains, selected_tools)
        llm = await create_llm_for_tier(model_tier, school_id, db)
    except Exception as pipeline_exc:
        # Pipeline 异常：fallback 到全工具集 + 默认模型
        logger.warning("Agent Pipeline failed, falling back: %s", pipeline_exc)
        profile = None
        selected_tools = None  # Agent.run() 会用 registry 全量
        model_tier = "standard"
        intent_resolver = None
        llm = LLMChatClient(
            api_url=settings.LLM_API_URL,
            api_key=settings.LLM_API_KEY,
            model=settings.LLM_MODEL,
            timeout=settings.LLM_TIMEOUT,
            max_retries=settings.LLM_MAX_RETRIES,
        )

    # Session context (multi-turn support) — N-03: 用 selected_tools 名称重建 system prompt
    if session_id not in _sessions:
        if selected_tools is not None:
            tool_names = [t.name for t in selected_tools]
        else:
            tool_names = tools.list_tools()
        system_content = build_system_prompt(role, user.display_name, scope, tool_names)
        _sessions[session_id] = _SessionState(
            context=AgentContext(system_content=system_content),
            anonymizer=Anonymizer(),
        )
    session_state = _sessions[session_id]

    agent = Agent(llm=llm, registry=tools)

    async def event_stream():
        try:
            async for event in agent.run(
                user_message=message,
                session_id=session_id,
                db=db,
                school_id=school_id,
                class_ids=getattr(role_obj, "class_ids", None),
                role=role,
                display_name=user.display_name,
                scope=scope,
                audit=audit,
                user_id=user.id,
                context=session_state.context,
                anonymizer=session_state.anonymizer,
                tools=selected_tools,
            ):
                yield f"data: {json.dumps(event.to_dict(), ensure_ascii=False)}\n\n"
        finally:
            await llm.close()
            # Record AgentRun
            if profile is not None:
                try:
                    await AgentProfileService.record_run(
                        db,
                        profile_id=profile.id,
                        session_id=session_id,
                        tools_resolved=[t.name for t in available_tools] if selected_tools else [],
                        tools_selected=[t.name for t in selected_tools] if selected_tools else [],
                        model_used=llm.model,
                        model_tier=model_tier,
                        intent_domains=intent_resolver.last_domains if intent_resolver else [],
                    )
                    await db.commit()
                except Exception as rec_exc:
                    logger.warning("Failed to record AgentRun: %s", rec_exc)
        yield f"data: {json.dumps({'type': 'done', 'session_id': session_id})}\n\n"

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={"X-Session-Id": session_id},
    )


@router.get("/sessions")
async def list_sessions(current=Depends(get_current_user)):
    return {"sessions": list(_sessions.keys())}


@router.delete("/sessions/{session_id}")
async def delete_session(
    session_id: str,
    current=Depends(get_current_user),
):
    _sessions.pop(session_id, None)
    return {"deleted": True}
