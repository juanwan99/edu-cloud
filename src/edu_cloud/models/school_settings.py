from sqlalchemy import String, Boolean, Text, ForeignKey, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from edu_cloud.models.base import Base, IdMixin, TimestampMixin


class SchoolSetting(Base, IdMixin, TimestampMixin):
    """School-level key-value configuration."""
    __tablename__ = "school_settings"
    __table_args__ = (
        UniqueConstraint("school_id", "key", name="uq_school_settings_school_key"),
    )

    school_id: Mapped[str] = mapped_column(String(36), ForeignKey("schools.id"), index=True)
    category: Mapped[str] = mapped_column(String(50))
    key: Mapped[str] = mapped_column(String(100))
    value: Mapped[str | None] = mapped_column(Text, default=None)


# Default module codes and their display names
MODULE_CODES = {
    "exam": "考试管理",
    "grading": "阅卷系统",
    "homework": "作业管理",
    "study_analytics": "学情分析",
    "research": "教研题库",
    "teaching": "教学管理",
    "calendar": "校历日程",
    "studio": "文档中心",
}

# Modules enabled by default for new schools
DEFAULT_ENABLED = {"exam", "grading", "homework", "calendar", "studio"}


class SchoolModule(Base, IdMixin, TimestampMixin):
    """Module enable/disable per school."""
    __tablename__ = "school_modules"
    __table_args__ = (
        UniqueConstraint("school_id", "module_code", name="uq_school_modules_school_code"),
    )

    school_id: Mapped[str] = mapped_column(String(36), ForeignKey("schools.id"), index=True)
    module_code: Mapped[str] = mapped_column(String(50))
    enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    config: Mapped[str | None] = mapped_column(Text, default=None)
