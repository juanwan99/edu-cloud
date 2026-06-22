"""Cross-module data boundary for homework remediation workflows.

This module centralizes the exam / scan / bank symbols used by homework's
post-exam remedial task generation and content expansion, so the homework module
no longer imports those modules directly. It removes the three direct
`homework -> {exam, scan, bank}` dependency edges tracked by D-03N.

The owner modules still define the ORM models. This service is a pure re-export
facade: homework code imports the same class objects through one application
service boundary, preserving runtime behavior while making the dependency graph
explicit.
"""
from edu_cloud.modules.bank.models import BankQuestion
from edu_cloud.modules.exam.models import (
    Exam,
    Question,
    Subject,
)
from edu_cloud.modules.scan.models import StudentAnswer

__all__ = [
    "Exam",
    "Subject",
    "Question",
    "StudentAnswer",
    "BankQuestion",
]
