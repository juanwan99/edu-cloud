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
from edu_cloud.ai.agent import Agent, ROLE_TOOL_CATEGORIES
from edu_cloud.ai.llm import LLMChatClient
from edu_cloud.ai.registry import tools
from edu_cloud.ai.audit import AuditLogger
from edu_cloud.ai.context import AgentContext, build_system_prompt
from edu_cloud.ai.anonymizer import Anonymizer
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

    # Session context (multi-turn support)
    if session_id not in _sessions:
        categories = ROLE_TOOL_CATEGORIES.get(role, [])
        tool_schemas = tools.get_schemas(categories=categories)
        tool_names = [s["function"]["name"] for s in tool_schemas]
        system_content = build_system_prompt(role, user.display_name, scope, tool_names)
        _sessions[session_id] = _SessionState(
            context=AgentContext(system_content=system_content),
            anonymizer=Anonymizer(),
        )
    session_state = _sessions[session_id]

    # LLM client
    llm = LLMChatClient(
        api_url=settings.LLM_API_URL,
        api_key=settings.LLM_API_KEY,
        model=settings.LLM_MODEL,
        timeout=settings.LLM_TIMEOUT,
        max_retries=settings.LLM_MAX_RETRIES,
    )

    agent = Agent(llm=llm, registry=tools)

    async def event_stream():
        try:
            async for event in agent.run(
                user_message=message,
                session_id=session_id,
                db=db,
                school_id=getattr(role_obj, "school_id", None),
                class_ids=getattr(role_obj, "class_ids", None),
                role=role,
                display_name=user.display_name,
                scope=scope,
                audit=audit,
                user_id=user.id,
                context=session_state.context,
                anonymizer=session_state.anonymizer,
            ):
                yield f"data: {json.dumps(event.to_dict(), ensure_ascii=False)}\n\n"
        finally:
            await llm.close()
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
