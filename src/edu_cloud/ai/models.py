from sqlalchemy import Column, String, JSON, Float, ForeignKey, Text
from edu_cloud.models.base import Base, IdMixin, TimestampMixin


class AiSession(Base, IdMixin, TimestampMixin):
    __tablename__ = "ai_sessions"
    user_id = Column(String, ForeignKey("users.id"), nullable=False)
    role = Column(String(50), nullable=False)
    school_id = Column(String, nullable=True)
    context_snapshot = Column(JSON, nullable=True)
    messages = Column(JSON, nullable=True)


class AiToolCall(Base, IdMixin, TimestampMixin):
    __tablename__ = "ai_tool_calls"
    session_id = Column(String, ForeignKey("ai_sessions.id"), nullable=False)
    user_id = Column(String, nullable=False)
    role = Column(String(50), nullable=False)
    tool = Column(String(100), nullable=False)
    arguments = Column(JSON, nullable=True)
    result_summary = Column(Text, nullable=True)
    duration_ms = Column(Float, nullable=True)
