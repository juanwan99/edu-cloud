import pytest
from edu_cloud.ai.tool_context import ToolContext, ToolResult


def test_tool_result_success():
    r = ToolResult(success=True, data={"avg": 85.2})
    assert r.success is True
    assert r.data == {"avg": 85.2}
    assert r.error is None
    assert r.is_read_only is True


def test_tool_result_failure():
    r = ToolResult(success=False, data=None, error="exam not found")
    assert r.success is False
    assert r.error == "exam not found"


def test_tool_result_to_dict():
    r = ToolResult(success=True, data={"count": 3}, metadata={"duration_ms": 42})
    d = r.to_dict()
    assert d["success"] is True
    assert d["data"] == {"count": 3}
    assert d["metadata"]["duration_ms"] == 42


def test_tool_result_to_dict_omits_none():
    r = ToolResult(success=True, data=None)
    d = r.to_dict()
    assert "error" not in d
    assert "metadata" not in d


def test_tool_context_fields():
    ctx = ToolContext(
        db=None,
        school_id="S001",
        user_id="U001",
        role="academic_director",
        class_ids=["C1", "C2"],
        subject_codes=["SX"],
        grade_ids=None,
        capabilities={("analytics", "read"): True},
        enabled_modules=["exam", "grading"],
        anonymizer=None,
    )
    assert ctx.school_id == "S001"
    assert ctx.role == "academic_director"
    assert ctx.class_ids == ["C1", "C2"]
