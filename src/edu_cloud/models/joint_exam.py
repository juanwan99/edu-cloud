"""联考模型：跨校考试的编排与追踪。"""

from datetime import datetime, timezone
from sqlalchemy import String, Integer, Float, Text, ForeignKey, JSON, Boolean, DateTime, UniqueConstraint, Index
from sqlalchemy.orm import Mapped, mapped_column
from edu_cloud.models.base import Base, IdMixin, TimestampMixin


class JointExam(Base, IdMixin, TimestampMixin):
    """联考主表。"""
    __tablename__ = "joint_exams"

    name: Mapped[str] = mapped_column(String(200))
    description: Mapped[str | None] = mapped_column(Text, default=None)
    created_by: Mapped[str] = mapped_column(String(36), ForeignKey("platform_users.id"))
    status: Mapped[str] = mapped_column(String(20), default="draft")
    # status: draft → templates_ready → distributed → collecting → completed → archived

    subjects: Mapped[list] = mapped_column(JSON, default=list)
    # [{"code": "YW", "name": "语文", "max_score": 150}, ...]

    # 新增字段
    creator_school_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("registered_schools.id"), default=None
    )
    template_file_path: Mapped[str | None] = mapped_column(String(500), default=None)
    answer_detail_schema: Mapped[dict | None] = mapped_column(JSON, default=None)
    # {"YW": [{"id": "q1", "max_score": 10, "type": "主观题"}, ...]}


class JointExamParticipant(Base, IdMixin, TimestampMixin):
    """联考参与学校。"""
    __tablename__ = "joint_exam_participants"

    joint_exam_id: Mapped[str] = mapped_column(String(36), ForeignKey("joint_exams.id"))
    school_id: Mapped[str] = mapped_column(String(36), ForeignKey("registered_schools.id"))
    status: Mapped[str] = mapped_column(String(20), default="pending")
    # status: pending → scores_uploaded
    is_creator: Mapped[bool] = mapped_column(Boolean, default=False)

    student_count: Mapped[int | None] = mapped_column(Integer, default=None)
    score_upload_count: Mapped[int | None] = mapped_column(Integer, default=None)


class JointExamStudentResult(Base, IdMixin, TimestampMixin):
    """联考学生成绩明细（替代旧 JointExamScore）。"""
    __tablename__ = "joint_exam_student_results"

    joint_exam_id: Mapped[str] = mapped_column(String(36), ForeignKey("joint_exams.id"))
    school_id: Mapped[str] = mapped_column(String(36), ForeignKey("registered_schools.id"))
    subject_code: Mapped[str] = mapped_column(String(50))
    student_name: Mapped[str] = mapped_column(String(100))
    student_number: Mapped[str] = mapped_column(String(100))
    total_score: Mapped[float] = mapped_column(Float)
    detail_scores: Mapped[list] = mapped_column(JSON, default=list)
    # [{"question_id": "q1", "score": 5.0, "max_score": 10.0}, ...]
    uploaded_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )

    __table_args__ = (
        UniqueConstraint(
            "joint_exam_id", "school_id", "subject_code", "student_number",
            name="uq_result_student",
        ),
        Index("ix_result_ranking", "joint_exam_id", "subject_code", "total_score"),
        Index("ix_result_school", "joint_exam_id", "school_id"),
    )
