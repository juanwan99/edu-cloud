"""Facade for bank workflows that read data owned by other modules."""

from edu_cloud.modules.exam.models import Question, Subject
from edu_cloud.modules.student.models import Student

__all__ = ["Question", "Student", "Subject"]
