"""Cross-module data boundary for the grading workflow.

This module centralizes the exam / card / scan symbols used by grading routers,
so the grading module no longer imports those modules directly. It removes the
three direct `grading -> {exam, card, scan}` dependency edges tracked by D-03M.

The owner modules still define the ORM models, constants, ordering helpers,
slot selector, and scan pipeline state helpers. This service is a pure re-export
facade: grading code imports the same objects through one application-service
boundary, preserving runtime behavior while making the dependency graph explicit.
"""
from edu_cloud.modules.card.models import Template
from edu_cloud.modules.exam.models import (
    Exam,
    Question,
    QUESTION_TYPES_SUBJECTIVE,
    Subject,
)
from edu_cloud.modules.exam.question_order import question_sort_key
from edu_cloud.modules.exam.slot_selector import SLOT_AI_GRADING, get_llm_config
from edu_cloud.modules.scan import pipeline_service
from edu_cloud.modules.scan.models import StudentAnswer

__all__ = [
    "Exam",
    "Question",
    "QUESTION_TYPES_SUBJECTIVE",
    "Subject",
    "question_sort_key",
    "SLOT_AI_GRADING",
    "get_llm_config",
    "pipeline_service",
    "StudentAnswer",
    "Template",
]
