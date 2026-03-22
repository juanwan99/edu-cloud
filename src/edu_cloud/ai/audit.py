import logging
from sqlalchemy.ext.asyncio import AsyncSession
from edu_cloud.models.ai_session import AiSession, AiToolCall

logger = logging.getLogger(__name__)


class AuditLogger:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create_session(self, user_id: str, role: str, context: dict | None = None) -> str:
        session = AiSession(user_id=user_id, role=role, context_snapshot=context)
        self.db.add(session)
        await self.db.flush()
        return session.id

    async def log_tool_call(self, session_id, user_id, role, tool, arguments, result, duration_ms):
        summary = result[:500] if result else ""
        self.db.add(AiToolCall(
            session_id=session_id, user_id=user_id, role=role,
            tool=tool, arguments=arguments, result_summary=summary, duration_ms=duration_ms,
        ))
        await self.db.flush()
