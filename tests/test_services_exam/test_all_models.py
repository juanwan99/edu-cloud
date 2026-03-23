"""Smoke test: all models can create tables."""
import pytest


async def test_all_tables_created(db):
    """If we get here, conftest created all tables from Base.metadata."""
    from edu_cloud.models.base import Base
    table_names = set(Base.metadata.tables.keys())
    expected = {
        "schools", "users", "exams", "subjects", "templates", "questions",
        "scan_tasks", "student_answers",
        "grading_tasks", "ai_grading_results", "teacher_reviews",
        "classes", "students", "marking_assignments",
    }
    assert expected.issubset(table_names)
