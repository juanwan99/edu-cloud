"""Facade for academic workflows that compose calendar and student data."""

from edu_cloud.modules.calendar import teaching_plan_service
from edu_cloud.modules.student.models import Class

__all__ = ["Class", "teaching_plan_service"]
