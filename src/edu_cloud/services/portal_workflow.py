"""Facade for portal aggregation workflows that compose source modules."""

from edu_cloud.modules.calendar.service import CalendarService
from edu_cloud.modules.homework.service import HomeworkTaskService

__all__ = ["CalendarService", "HomeworkTaskService"]
