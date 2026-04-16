import pytest
from edu_cloud.ai.grounded import DataSource
from edu_cloud.ai.tool_context import ToolResult


class TestDataSource:
    def test_create(self):
        ds = DataSource(type="db_query", table="exam_scores", ref="2026期中", queried_at="2026-04-05T20:30:00")
        assert ds.type == "db_query"
        assert ds.table == "exam_scores"

    def test_frozen(self):
        ds = DataSource(type="db_query", table="t", ref="r", queried_at="now")
        with pytest.raises(AttributeError):
            ds.type = "other"

    def test_to_dict(self):
        ds = DataSource(type="db_query", table="exam_scores", ref="期中", queried_at="2026-04-05T20:30:00")
        d = ds.to_dict()
        assert d["type"] == "db_query"
        assert d["table"] == "exam_scores"


class TestToolResultSource:
    def test_source_default_none(self):
        r = ToolResult(success=True, data={"avg": 72})
        assert r.source is None

    def test_source_with_data(self):
        ds = DataSource(type="db_query", table="exam_scores", ref="期中", queried_at="now")
        r = ToolResult(success=True, data={"avg": 72}, source=ds)
        assert r.source.type == "db_query"

    def test_to_dict_without_source(self):
        r = ToolResult(success=True, data={"avg": 72})
        d = r.to_dict()
        assert "source" not in d

    def test_to_dict_with_source(self):
        ds = DataSource(type="db_query", table="exam_scores", ref="期中", queried_at="now")
        r = ToolResult(success=True, data={"avg": 72}, source=ds)
        d = r.to_dict()
        assert d["source"]["type"] == "db_query"

    def test_backward_compat_existing_usage(self):
        """Existing code creates ToolResult without source — must still work."""
        r = ToolResult(success=True, data=[{"id": "1"}])
        assert r.success
        r2 = ToolResult(success=False, error="fail")
        assert r2.error == "fail"


from edu_cloud.ai.grounded import OutputValidator, ValidationResult


class TestOutputValidator:
    def setup_method(self):
        self.validator = OutputValidator()

    def test_no_tools_pass(self):
        result = self.validator.validate("你好，有什么可以帮你的？", [])
        assert result.status == "pass"

    def test_no_numbers_pass(self):
        tr = ToolResult(success=True, data={"avg": 72.3})
        result = self.validator.validate("成绩整体还不错", [tr])
        assert result.status == "pass"

    def test_matching_number_pass(self):
        tr = ToolResult(success=True, data={"avg": 72.3})
        result = self.validator.validate("班级平均分 72.3 分", [tr])
        assert result.status == "pass"

    def test_matching_percentage_pass(self):
        tr = ToolResult(success=True, data={"excellent_rate": 0.38})
        result = self.validator.validate("优秀率 38%", [tr])
        assert result.status == "pass"

    def test_contradicting_number_fail(self):
        tr = ToolResult(success=True, data={"avg": 72.3})
        result = self.validator.validate("班级平均分 85 分", [tr])
        assert result.status == "fail"

    def test_ungrounded_number_warn(self):
        """98 分 with closest tool value 72.3 → fail (score tolerance 0.5%)."""
        tr = ToolResult(success=True, data={"avg": 72.3})
        result = self.validator.validate("班级平均分 72.3 分，最高分 98 分", [tr])
        # P2-1: with typed tolerance, 98 vs 72.3 is a contradiction (not just ungrounded)
        assert result.status == "fail"
        assert any(c["response"] == 98.0 for c in result.contradictions)

    def test_integer_float_match(self):
        tr = ToolResult(success=True, data={"count": 72})
        result = self.validator.validate("共 72 人", [tr])
        assert result.status == "pass"

    def test_nested_data(self):
        tr = ToolResult(success=True, data={"stats": {"avg": 72.3, "max": 98}})
        result = self.validator.validate("平均 72.3 分，最高 98 分", [tr])
        assert result.status == "pass"


class TestNumberToken:
    """P2-1: structured number extraction."""

    def test_extract_score_unit(self):
        v = OutputValidator()
        tokens = v._extract_number_tokens("平均分 85.3 分，最高 100 分")
        values = {t.value for t in tokens}
        assert 85.3 in values
        assert 100.0 in values
        assert all(t.unit == "分" for t in tokens)

    def test_extract_count_unit(self):
        v = OutputValidator()
        tokens = v._extract_number_tokens("共 42 人参加，3 班共 38 人")
        units = {t.unit for t in tokens}
        assert "人" in units

    def test_extract_percent_unit(self):
        v = OutputValidator()
        tokens = v._extract_number_tokens("及格率 85%")
        assert any(t.unit == "%" and t.value == 85.0 for t in tokens)


class TestTypedTolerance:
    """P2-1: type-specific validation tolerance."""

    def test_score_strict_tolerance(self):
        """Score 85.3 reported as 86 should be flagged (>0.5% error)."""
        v = OutputValidator()
        result = v.validate(
            "平均分 86 分",
            [ToolResult(success=True, data={"avg_score": 85.3})],
        )
        assert result.status == "fail"

    def test_score_within_tolerance(self):
        """Score 85.3 reported as 85.3 should pass."""
        v = OutputValidator()
        result = v.validate(
            "平均分 85.3 分",
            [ToolResult(success=True, data={"avg_score": 85.3})],
        )
        assert result.status == "pass"

    def test_count_must_be_exact(self):
        """Count must be exact — 42 reported as 43 is fail."""
        v = OutputValidator()
        result = v.validate(
            "共 43 人",
            [ToolResult(success=True, data={"student_count": 42})],
        )
        assert result.status == "fail"


class TestPercentConversion:
    """P2-2: conditional percent conversion."""

    def test_rate_field_converts(self):
        """Field named 'pass_rate' with value 0.85 should match '85%'."""
        v = OutputValidator()
        result = v.validate(
            "及格率 85%",
            [ToolResult(success=True, data={"pass_rate": 0.85})],
        )
        assert result.status == "pass"

    def test_non_rate_field_no_convert(self):
        """Field named 'coefficient' with value 0.85 should NOT match '85%'."""
        v = OutputValidator()
        result = v.validate(
            "系数 85%",
            [ToolResult(success=True, data={"coefficient": 0.85})],
        )
        # 0.85 does not auto-convert, so 85 is ungrounded
        assert result.status in ("warn", "fail")


class TestCrossUnitMismatch:
    """F003: tool value from different field should NOT ground different unit in response."""

    def test_count_value_does_not_ground_percent(self):
        """student_count=85 should NOT make '及格率 85%' pass."""
        v = OutputValidator()
        result = v.validate(
            "及格率 85%",
            [ToolResult(success=True, data={"student_count": 85})],
        )
        # 85 from student_count has no unit; 85% in response has unit "%"
        # They should NOT cross-match
        assert result.status in ("warn", "fail"), \
            "student_count=85 should not ground '85%' — different semantic contexts"

    def test_same_value_same_context_still_passes(self):
        """avg_score=85.3 should ground '平均分 85.3 分'."""
        v = OutputValidator()
        result = v.validate(
            "平均分 85.3 分",
            [ToolResult(success=True, data={"avg_score": 85.3})],
        )
        assert result.status == "pass"


class TestGroundedPrompt:
    def test_prompt_contains_grounded_rules(self):
        from edu_cloud.ai.prompts import build_teacher_prompt
        prompt = build_teacher_prompt(
            role="subject_teacher",
            display_name="李老师",
            school_name="育才中学",
            tool_names=["get_class_stats"],
            tier=1,
        )
        assert "数据引用规则" in prompt
        assert "禁止" in prompt
