"""班级模型（学校端同步）。"""
from sqlalchemy import Column, String, Integer, ForeignKey
from edu_cloud.models.base import Base, IdMixin, TimestampMixin


class ClassGroup(Base, IdMixin, TimestampMixin):
    __tablename__ = "class_groups"

    name = Column(String, nullable=False)
    grade = Column(String, nullable=False)
    grade_number = Column(Integer, nullable=True)
    school_id = Column(String, ForeignKey("registered_schools.id"), nullable=False)
