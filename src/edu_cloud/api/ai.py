import json
import logging
from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from edu_cloud.database import get_db
from edu_cloud.api.deps import require_permission
from edu_cloud.core.permissions import Permission
from edu_cloud.ai.agent import Agent
from edu_cloud.ai.llm import LLMClient
from edu_cloud.ai.registry import tools
from edu_cloud.ai.audit import AuditLogger
import edu_cloud.ai.tools  # noqa: F401 — trigger tool registration

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1/ai", tags=["ai"])


@router.get("/health")
async def ai_health():
    tool_count = len(tools.list_tools())
    return {"status": "ok", "tools": tool_count}


@router.post("/chat")
async def ai_chat(
    body: dict,
    current=Depends(require_permission(Permission.USE_AI_CHAT)),
    db: AsyncSession = Depends(get_db),
):
    message = body.get("message", "").strip()
    if not message:
        return {"error": "消息不能为空"}

    user = current["user"]
    role_obj = current["current_role"]
    role = role_obj.role if hasattr(role_obj, "role") else getattr(role_obj, "_role", "unknown")

    scope = {}
    if hasattr(role_obj, "school_id") and role_obj.school_id:
        scope["school"] = role_obj.school_id
    if hasattr(role_obj, "class_ids") and role_obj.class_ids:
        scope["classes"] = role_obj.class_ids
    if hasattr(role_obj, "grade_ids") and role_obj.grade_ids:
        scope["grades"] = role_obj.grade_ids
    if hasattr(role_obj, "subject_codes") and role_obj.subject_codes:
        scope["subjects"] = role_obj.subject_codes

    audit = AuditLogger(db)
    session_id = await audit.create_session(user.id, role, context=scope)

    llm = LLMClient()
    agent = Agent(llm=llm, registry=tools)

    async def event_stream():
        async for event in agent.run(
            user_message=message, session_id=session_id, db=db,
            school_id=getattr(role_obj, "school_id", None),
            class_ids=getattr(role_obj, "class_ids", None),
            role=role, display_name=user.display_name, scope=scope, audit=audit,
            user_id=user.id,
        ):
            yield f"data: {json.dumps(event.to_dict(), ensure_ascii=False)}\n\n"

    return StreamingResponse(event_stream(), media_type="text/event-stream")
