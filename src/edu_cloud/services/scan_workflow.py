"""Cross-module data boundary for the scan workflow.

This module centralizes the exam / card / student ORM models and question-type
constant used by scan routers, so the scan module no longer imports those
modules directly. It removes the three direct `scan -> {exam, card, student}`
dependency edges tracked by D-03L.

The owner modules still define the objects. This service is a pure re-export
facade: scan code imports the same class and constant objects through one
application-service boundary, preserving runtime behavior while making the
dependency graph explicit.

This follows the `services.marking_workflow` / `services.exam_import_materialization`
pattern. The dependency guard scans only `src/edu_cloud/modules/`, so services
can own these cross-module imports while module code consumes the facade.
"""
from edu_cloud.modules.card.models import Template
from edu_cloud.modules.exam.models import (
    Exam,
    Question,
    QUESTION_TYPES_OBJECTIVE,
    Subject,
)
from edu_cloud.modules.student.models import Student

__all__ = [
    "Exam",
    "Subject",
    "Question",
    "QUESTION_TYPES_OBJECTIVE",
    "Template",
    "Student",
]
