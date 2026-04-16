from sqlalchemy import Column, String, Date, Boolean, Integer, JSON, ForeignKey
from edu_cloud.models.base import Base, IdMixin, TimestampMixin


class CalendarEvent(Base, IdMixin, TimestampMixin):
    __tablename__ = "calendar_events"
    type = Column(String(50), nullable=False)         # holiday / exam / parent_meeting / deadline
    title = Column(String(200), nullable=False)
    description = Column(String(500), nullable=True)
    event_date = Column(Date, nullable=False)
    school_id = Column(String(36), ForeignKey("schools.id"), nullable=False)
    created_by = Column(String(36), ForeignKey("users.id"), nullable=False)
    semester = Column(String(20), nullable=True)      # "2025-2026-2"
    is_active = Column(Boolean, default=True, nullable=False)

    def __init__(self, **kwargs):
        kwargs.setdefault("is_active", True)
        super().__init__(**kwargs)


class NotificationRule(Base, IdMixin, TimestampMixin):
    __tablename__ = "notification_rules"
    event_id = Column(String(36), ForeignKey("calendar_events.id"), nullable=False)
    days_before = Column(Integer, nullable=False)      # 提前几天触发（7/3/1）
    template_type = Column(String(50), nullable=False)  # holiday_safety / exam_reminder / meeting_invite
    target_roles = Column(JSON, nullable=False)         # ["parent"] / ["homeroom_teacher", "parent"]
    auto_draft = Column(Boolean, default=True, nullable=False)
    triggered = Column(Boolean, default=False, nullable=False)  # 已触发标记，防重复
