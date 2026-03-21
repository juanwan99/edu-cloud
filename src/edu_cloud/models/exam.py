"""学校端考试 + 成绩结果模型（学校端同步）。"""
from sqlalchemy import Column, String, Float, ForeignKey, JSON, DateTime, UniqueConstraint
from edu_cloud.models.base import Base, IdMixin, TimestampMixin


class Exam(Base, IdMixin, TimestampMixin):
    __tablename__ = "exams"

    name = Column(String, nullable=False)
    subject_code = Column(String, nullable=False)
    subject_name = Column(String, nullable=True)
    max_score = Column(Float, nullable=True)
    school_id = Column(String, ForeignKey("registered_schools.id"), nullable=False)
    exam_date = Column(DateTime, nullable=True)
    semester = Column(String, nullable=True)
    source = Column(String, default="sync")


class ExamResult(Base, IdMixin, TimestampMixin):
    __tablename__ = "exam_results"

    exam_id = Column(String, ForeignKey("exams.id"), nullable=False)
    student_id = Column(String, ForeignKey("students.id"), nullable=False)
    school_id = Column(String, ForeignKey("registered_schools.id"), nullable=False)
    total_score = Column(Float, nullable=False)
    detail_scores = Column(JSON, nullable=True)

    __table_args__ = (
        UniqueConstraint("exam_id", "student_id", name="uq_result_exam_student"),
    )
