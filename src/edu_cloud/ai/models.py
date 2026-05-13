from sqlalchemy import Column, String, JSON, Float, ForeignKey, Index, Text
from sqlalchemy.orm import Mapped, mapped_column

from edu_cloud.models.base import Base, IdMixin, TimestampMixin


class AiSession(Base, IdMixin, TimestampMixin):
    __tablename__ = "ai_sessions"
    user_id = Column(String, ForeignKey("users.id"), nullable=False)
    role = Column(String(50), nullable=False)
    school_id = Column(String, nullable=True)
    context_snapshot = Column(JSON, nullable=True)
    messages = Column(JSON, nullable=True)


class AiChatMessage(Base, IdMixin, TimestampMixin):
    __tablename__ = "ai_chat_messages"

    session_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("ai_sessions.id", ondelete="CASCADE"), nullable=False,
    )
    role_in_chat: Mapped[str] = mapped_column(String(20), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    metadata_json: Mapped[str | None] = mapped_column(Text, nullable=True)

    __table_args__ = (
        Index("ix_ai_chat_messages_session_created", "session_id", "created_at"),
    )


class AiToolCall(Base, IdMixin, TimestampMixin):
    __tablename__ = "ai_tool_calls"
    session_id = Column(String, ForeignKey("ai_sessions.id", ondelete="CASCADE"), nullable=False)
    user_id = Column(String, nullable=False)
    role = Column(String(50), nullable=False)
    tool = Column(String(100), nullable=False)
    arguments = Column(JSON, nullable=True)
    result_summary = Column(Text, nullable=True)
    duration_ms = Column(Float, nullable=True)
