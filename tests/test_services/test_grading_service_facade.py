"""Tests for the grading Service facade re-exports.

Only verifies imports and object identity; does not touch the database or
the async runtime, and avoids broad imports.
"""
from edu_cloud.modules.grading import assignment_service, quality_service
from edu_cloud.modules.grading.service import (
    GradingAssignmentService,
    QualityCheckService,
)


def test_facade_imports_both_services():
    """Both classes can be imported from the facade module."""
    assert GradingAssignmentService is not None
    assert QualityCheckService is not None


def test_facade_reexports_same_class_objects():
    """The facade exports the exact same class objects as the source modules."""
    assert GradingAssignmentService is assignment_service.GradingAssignmentService
    assert QualityCheckService is quality_service.QualityCheckService


def test_facade_all_lists_exact_names():
    """__all__ declares exactly the two re-exported Service names."""
    from edu_cloud.modules.grading import service

    assert service.__all__ == ["GradingAssignmentService", "QualityCheckService"]
