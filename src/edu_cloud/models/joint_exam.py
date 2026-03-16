"""联考模型：跨校考试的编排与追踪。"""

from sqlalchemy import String, Integer, Float, Text, ForeignKey, JSON
from sqlalchemy.orm import Mapped, mapped_column
from edu_cloud.models.base import Base, IdMixin, TimestampMixin


class JointExam(Base, IdMixin, TimestampMixin):
    """联考主表：一次跨校联考。"""
    __tablename__ = "joint_exams"

    name: Mapped[str] = mapped_column(String(200))
    description: Mapped[str | None] = mapped_column(Text, default=None)
    created_by: Mapped[str] = mapped_column(String(36), ForeignKey("platform_users.id"))
    status: Mapped[str] = mapped_column(String(20), default="draft")
    # status: draft -> distributed -> scanning -> grading -> completed -> archived

    # 考试配置
    subjects: Mapped[list] = mapped_column(JSON, default=list)
    # e.g. [{"code": "YW", "name": "语文", "max_score": 150}, ...]


class JointExamParticipant(Base, IdMixin, TimestampMixin):
    """联考参与学校：哪些学校参加了这次联考。"""
    __tablename__ = "joint_exam_participants"

    joint_exam_id: Mapped[str] = mapped_column(String(36), ForeignKey("joint_exams.id"))
    school_id: Mapped[str] = mapped_column(String(36), ForeignKey("registered_schools.id"))
    status: Mapped[str] = mapped_column(String(20), default="pending")
    # status: pending -> accepted -> scanning -> scores_uploaded -> completed

    # 该校上报的数据摘要
    student_count: Mapped[int | None] = mapped_column(Integer, default=None)
    score_upload_count: Mapped[int | None] = mapped_column(Integer, default=None)


class JointExamScore(Base, IdMixin, TimestampMixin):
    """联考成绩：各校上报的学生成绩汇总。"""
    __tablename__ = "joint_exam_scores"

    joint_exam_id: Mapped[str] = mapped_column(String(36), ForeignKey("joint_exams.id"))
    school_id: Mapped[str] = mapped_column(String(36), ForeignKey("registered_schools.id"))
    subject_code: Mapped[str] = mapped_column(String(50))
    student_id: Mapped[str] = mapped_column(String(100))  # 学校端的学生 ID
    student_name: Mapped[str] = mapped_column(String(100))
    class_name: Mapped[str | None] = mapped_column(String(100), default=None)
    score: Mapped[float] = mapped_column(Float)
    max_score: Mapped[float] = mapped_column(Float)
