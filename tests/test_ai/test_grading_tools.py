import pytest


def test_grading_tools_registered():
    from edu_cloud.ai.tools import grading_ops  # noqa: F401
    from edu_cloud.ai.registry import tools
    names = tools.list_tools()
    assert "get_grading_progress" in names
    assert "get_quality_report" in names
    assert "assign_grading_task" in names


def test_grading_tools_metadata():
    """CR-04: 验证 grading 工具的完整元数据（domain/module_code/risk_level/allowed_roles）"""
    from edu_cloud.ai.registry import tools
    specs = {s.name: s for s in tools.get_all_specs()}

    progress = specs["get_grading_progress"]
    assert progress.category == "L1_exam"
    assert progress.module_code == "grading"
    assert progress.domain == "exam"
    assert progress.risk_level == "low"
    assert "platform_admin" in progress.allowed_roles
    assert "subject_teacher" in progress.allowed_roles

    quality = specs["get_quality_report"]
    assert quality.category == "L2_analytics"
    assert quality.module_code == "grading"
    assert quality.domain == "exam"
    assert quality.risk_level == "low"
    assert "platform_admin" in quality.allowed_roles
    assert "academic_director" in quality.allowed_roles
    assert "subject_teacher" not in quality.allowed_roles

    assign = specs["assign_grading_task"]
    assert assign.category == "L4_action"
    assert assign.module_code == "grading"
    assert assign.domain == "exam"
    assert assign.risk_level == "med"
    assert "platform_admin" in assign.allowed_roles
    assert "academic_director" in assign.allowed_roles
    assert "subject_teacher" not in assign.allowed_roles
