import pytest


def test_grading_tools_registered():
    from edu_cloud.ai.tools import grading_ops  # noqa: F401
    from edu_cloud.ai.registry import tools
    names = tools.list_tools()
    assert "get_grading_progress" in names
    assert "get_quality_report" in names
    assert "assign_grading_task" in names


def test_grading_tools_metadata():
    """F-05: Phase 1d 元数据参数尚未合入，仅验证基础注册属性"""
    from edu_cloud.ai.registry import tools
    specs = {s.name: s for s in tools.get_all_specs()}

    progress = specs["get_grading_progress"]
    assert progress.category == "L1_exam"

    assign = specs["assign_grading_task"]
    assert assign.category == "L4_action"
