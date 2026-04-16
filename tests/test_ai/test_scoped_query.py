"""Tests for ScopedQuery — unified scope-aware data filter."""
import pytest
from sqlalchemy import select

from edu_cloud.ai.data_scope import DataScope
from edu_cloud.ai.scoped_query import ScopedQuery, ScopeViolationError
from edu_cloud.modules.profile.models import StudentExamSnapshot
from edu_cloud.modules.student.models import Class


def _make_scope(**overrides):
    """Helper to create DataScope with defaults."""
    defaults = dict(
        user_id="u1",
        school_id="s1",
        role="subject_teacher",
        visible_class_ids=None,
        visible_subject_codes=None,
        visible_grade_ids=None,
        visible_student_ids=None,
        district_ids=None,
        can_write=True,
        can_see_rankings=True,
        can_cross_school=False,
        persona="teacher_assistant",
        version=1,
    )
    defaults.update(overrides)
    return DataScope(**defaults)


def _compile(query) -> str:
    return str(query.compile(compile_kwargs={"literal_binds": True}))


class TestScopedQueryApply:
    """Tests for ScopedQuery.apply() SQL injection."""

    def test_scoped_query_injects_school_id(self):
        scope = _make_scope(school_id="school-1")
        sq = ScopedQuery(db=None, scope=scope)
        query = select(StudentExamSnapshot)
        filtered = sq.apply(query, StudentExamSnapshot)
        sql = _compile(filtered)
        assert "school_id" in sql
        assert "school-1" in sql

    def test_scoped_query_admin_no_class_filter(self):
        scope = _make_scope(
            role="platform_admin",
            can_cross_school=True,
            visible_class_ids=None,
            visible_subject_codes=None,
            visible_student_ids=None,
        )
        sq = ScopedQuery(db=None, scope=scope)
        query = select(StudentExamSnapshot)
        filtered = sq.apply(query, StudentExamSnapshot)
        sql = _compile(filtered)
        # Admin with can_cross_school should not have class_id filter
        assert "class_id" not in sql.lower().split("where")[-1] if "where" in sql.lower() else True

    def test_scoped_query_parent_locks_student_ids(self):
        scope = _make_scope(
            role="parent",
            visible_student_ids=["student-child-1"],
            can_cross_school=False,
        )
        sq = ScopedQuery(db=None, scope=scope)
        query = select(StudentExamSnapshot)
        filtered = sq.apply(query, StudentExamSnapshot)
        sql = _compile(filtered)
        assert "student_id" in sql
        assert "student-child-1" in sql

    def test_scoped_query_subject_filter(self):
        scope = _make_scope(visible_subject_codes=["math", "physics"])
        sq = ScopedQuery(db=None, scope=scope)
        query = select(StudentExamSnapshot)
        filtered = sq.apply(query, StudentExamSnapshot)
        sql = _compile(filtered)
        assert "subject_code" in sql
        assert "math" in sql

    def test_cross_school_skips_school_filter(self):
        scope = _make_scope(school_id="school-1", can_cross_school=True)
        sq = ScopedQuery(db=None, scope=scope)
        query = select(StudentExamSnapshot)
        filtered = sq.apply(query, StudentExamSnapshot)
        sql = _compile(filtered)
        # Should not contain school-1 as a filter value
        assert "school-1" not in sql

    def test_class_filter_with_custom_class_col(self):
        """F002: class filtering works when class_col='class_id_at_exam' is passed
        for StudentExamSnapshot (which uses class_id_at_exam, not class_id)."""
        scope = _make_scope(visible_class_ids=["cls-1", "cls-2"])
        sq = ScopedQuery(db=None, scope=scope)
        query = select(StudentExamSnapshot)
        filtered = sq.apply(
            query, StudentExamSnapshot, class_col="class_id_at_exam"
        )
        sql = _compile(filtered)
        assert "class_id_at_exam" in sql
        assert "cls-1" in sql
        assert "cls-2" in sql

    def test_class_filter_default_col_on_model_with_class_id(self):
        """F002/F004: default class_col='class_id' works on models that have it
        (e.g. Class model has no class_id column directly, but we can verify
        the filter does NOT silently skip when the column exists)."""
        # StudentExamSnapshot does NOT have class_id → default filter is skipped
        scope = _make_scope(visible_class_ids=["cls-1"])
        sq = ScopedQuery(db=None, scope=scope)
        query = select(StudentExamSnapshot)
        filtered = sq.apply(query, StudentExamSnapshot)
        sql = _compile(filtered)
        # class_id should NOT appear because StudentExamSnapshot lacks class_id attr
        assert "cls-1" not in sql, (
            "Default class_col='class_id' should be skipped for StudentExamSnapshot"
        )

    def test_class_filter_default_col_applied_when_present(self):
        """F004: verify DEFAULT class_col='class_id' works on model that HAS class_id.
        Uses ClassExamReport which has a real class_id column.
        If the class filtering code is deleted, this test WILL fail."""
        from edu_cloud.models.agent_snapshot import ClassExamReport
        scope = _make_scope(visible_class_ids=["cls-99"])
        sq = ScopedQuery(db=None, scope=scope)
        query = select(ClassExamReport)
        # No class_col override — uses default "class_id"
        filtered = sq.apply(query, ClassExamReport)
        sql = _compile(filtered)
        assert "cls-99" in sql, "Default class_col='class_id' must inject WHERE clause on ClassExamReport"


class TestScopedQueryValidateParam:
    """Tests for ScopedQuery.validate_param() amplification guard."""

    def test_rejects_amplification(self):
        scope = _make_scope(visible_class_ids=["c1", "c2"])
        sq = ScopedQuery(db=None, scope=scope)
        with pytest.raises(ScopeViolationError, match="class_id=forbidden"):
            sq.validate_param("class_id", "forbidden")

    def test_passes_for_allowed(self):
        scope = _make_scope(visible_class_ids=["c1", "c2"])
        sq = ScopedQuery(db=None, scope=scope)
        # Should not raise
        sq.validate_param("class_id", "c1")

    def test_none_means_no_limit(self):
        scope = _make_scope(visible_class_ids=None)
        sq = ScopedQuery(db=None, scope=scope)
        # Should not raise — None means no restriction
        sq.validate_param("class_id", "anything")

    def test_rejects_student_id_amplification(self):
        scope = _make_scope(visible_student_ids=["s1"])
        sq = ScopedQuery(db=None, scope=scope)
        with pytest.raises(ScopeViolationError):
            sq.validate_param("student_id", "s999")

    def test_rejects_subject_code_amplification(self):
        scope = _make_scope(visible_subject_codes=["math"])
        sq = ScopedQuery(db=None, scope=scope)
        with pytest.raises(ScopeViolationError):
            sq.validate_param("subject_code", "physics")
