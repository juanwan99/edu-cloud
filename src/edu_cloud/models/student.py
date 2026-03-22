"""学生档案模型（学校端同步）。"""
from sqlalchemy import Column, String, ForeignKey, UniqueConstraint
from edu_cloud.models.base import Base, IdMixin, TimestampMixin


class Student(Base, IdMixin, TimestampMixin):
    __tablename__ = "students"

    name = Column(String, nullable=False)
    student_number = Column(String, nullable=False)
    school_id = Column(String, ForeignKey("schools.id"), nullable=False)
    class_id = Column(String, nullable=True)
    grade = Column(String, nullable=True)
    gender = Column(String, nullable=True)

    __table_args__ = (
        UniqueConstraint("school_id", "student_number", name="uq_student_school_number"),
    )
