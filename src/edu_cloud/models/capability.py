from sqlalchemy import String, Boolean, ForeignKey, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from edu_cloud.models.base import Base, IdMixin, TimestampMixin


# 9 个域对齐 MODULE_CODES + system 管理域
CAPABILITY_DOMAINS = {
    "exam": "考试管理",
    "grading": "阅卷系统",
    "homework": "作业管理",
    "study_analytics": "学情分析",
    "research": "教研题库",
    "teaching": "教学管理",
    "calendar": "校历日程",
    "studio": "文档中心",
    "system": "系统管理",
}

CAPABILITY_ACTIONS = {"read", "write"}


class Capability(Base, IdMixin, TimestampMixin):
    """学校级角色能力配置：域×操作×角色。"""
    __tablename__ = "capabilities"
    __table_args__ = (
        UniqueConstraint("school_id", "role", "domain", "action",
                         name="uq_capability"),
    )

    school_id: Mapped[str] = mapped_column(String(36), ForeignKey("schools.id"), index=True)
    role: Mapped[str] = mapped_column(String(50))
    domain: Mapped[str] = mapped_column(String(50))
    action: Mapped[str] = mapped_column(String(20))
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
