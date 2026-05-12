"""Tests for ArtifactManager — large result deidentification + storage."""
from __future__ import annotations

from edu_cloud.ai.engine.artifact_manager import ArtifactManager, INLINE_MAX_ROWS


def _mgr() -> ArtifactManager:
    return ArtifactManager(run_id="run1", school_id="s1")


def test_small_result_stays_inline():
    mgr = _mgr()
    result = {"average": 85.5, "count": 30}
    assert not mgr.should_artifact(result, "school")


def test_large_list_triggers_artifact():
    mgr = _mgr()
    result = [{"name": f"student_{i}", "score": 80 + i} for i in range(60)]
    assert mgr.should_artifact(result, "school")


def test_pii_sensitivity_always_artifacts():
    mgr = _mgr()
    assert mgr.should_artifact({"name": "张三"}, "pii")


def test_process_result_inline():
    mgr = _mgr()
    result = {"avg": 85}
    processed = mgr.process_result("tool1", result, "school")
    assert processed == result
    assert len(mgr.artifacts) == 0


def test_process_result_artifact():
    mgr = _mgr()
    result = [{"id": i, "score": 80} for i in range(INLINE_MAX_ROWS + 10)]
    processed = mgr.process_result("get_scores", result, "student")
    assert processed["_artifact"] is True
    assert "artifact_id" in processed
    assert processed["summary"]["row_count"] == INLINE_MAX_ROWS + 10
    assert len(mgr.artifacts) == 1


def test_artifact_preview_truncates():
    mgr = _mgr()
    result = [{"id": i} for i in range(100)]
    processed = mgr.process_result("tool1", result, "school")
    assert processed["preview"]["truncated"] is True
    assert len(processed["preview"]["sample"]) == 5


def test_artifact_preview_redacts_pii():
    mgr = _mgr()
    result = [
        {"student_name": "张三", "score": 92, "student_number": "2024001"},
        {"student_name": "李四", "score": 85, "student_number": "2024002"},
    ] * 30  # > INLINE_MAX_ROWS
    processed = mgr.process_result("get_roster", result, "student")
    preview_sample = processed["preview"]["sample"]
    for row in preview_sample:
        assert row["student_name"] == "***"
        assert row["student_number"] == "***"
        assert isinstance(row["score"], int)


def test_get_artifact_by_id():
    mgr = _mgr()
    result = [{"x": i} for i in range(100)]
    processed = mgr.process_result("tool1", result, "school")
    art = mgr.get_artifact(processed["artifact_id"])
    assert art is not None
    assert art.source_tool == "tool1"
    assert art.raw_data == result


def test_artifact_kind_inference():
    mgr = _mgr()
    list_art = mgr.create_artifact("t1", [1, 2, 3] * 20, "school")
    assert list_art.kind == "table"

    dict_art = mgr.create_artifact("t2", {"key": "val"}, "school")
    assert dict_art.kind == "record"

    str_art = mgr.create_artifact("t3", "hello" * 1000, "public")
    assert str_art.kind == "text"
