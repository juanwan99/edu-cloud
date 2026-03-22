from sqlalchemy import Column, String, JSON, ForeignKey, DateTime
from edu_cloud.models.base import Base, IdMixin, TimestampMixin


class Notification(Base, IdMixin, TimestampMixin):
    __tablename__ = "notifications"
    document_id = Column(String(36), ForeignKey("documents.id"), nullable=False)
    channel = Column(String(20), nullable=False, default="wechat")  # wechat / sms / stub
    status = Column(String(20), nullable=False, default="pending")   # pending / sent / partial / failed
    target_scope = Column(JSON, nullable=True)       # {"class_ids": [...]} 或 {"school_id": "..."}
    school_id = Column(String(36), ForeignKey("registered_schools.id"), nullable=False)
    sent_at = Column(DateTime, nullable=True)
    result_summary = Column(JSON, nullable=True)      # {"total": 45, "success": 43, "unreachable": 2}

    def __init__(self, **kwargs):
        kwargs.setdefault("status", "pending")
        kwargs.setdefault("channel", "wechat")
        super().__init__(**kwargs)
