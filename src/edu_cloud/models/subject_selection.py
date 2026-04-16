from sqlalchemy import String, Boolean, JSON, ForeignKey, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from edu_cloud.models.base import Base, IdMixin, TimestampMixin

VALID_MODES = {"3+1+2", "3+3", "custom"}


class SubjectSelection(Base, IdMixin, TimestampMixin):
    """学校提供的选考科目组合。"""
    __tablename__ = "subject_selections"
    __table_args__ = (
        UniqueConstraint("school_id", "name", name="uq_subject_selection_name"),
    )

    school_id: Mapped[str] = mapped_column(String(36), ForeignKey("schools.id"), index=True)
    name: Mapped[str] = mapped_column(String(50))
    subject_codes: Mapped[list] = mapped_column(JSON)
    mode: Mapped[str] = mapped_column(String(20), default="custom")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
