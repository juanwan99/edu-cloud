"""Sprint 3 — new tool registration + basic tests."""
import pytest

from edu_cloud.ai.engine.tool_wrapper import TOOL_META_REGISTRY


def test_assign_remedial_homework_registered():
    """S3-T1: assign_remedial_homework is registered with correct metadata."""
    from edu_cloud.ai.engine.tools.homework import assign_remedial_homework
    meta = getattr(assign_remedial_homework, "_edu_meta", None)
    assert meta is not None
    assert meta.name == "assign_remedial_homework"
    assert meta.module_code == "homework"
    assert meta.risk_level == "medium"
    assert meta.is_read_only is False
    assert "assign_remedial_homework" in TOOL_META_REGISTRY


def test_draft_parent_notification_registered():
    """S3-T2: draft_parent_notification is registered with correct metadata."""
    from edu_cloud.ai.engine.tools.actions import draft_parent_notification
    meta = getattr(draft_parent_notification, "_edu_meta", None)
    assert meta is not None
    assert meta.name == "draft_parent_notification"
    assert meta.module_code == "conduct"
    assert meta.risk_level == "high"
    assert meta.is_read_only is False
    assert "draft_parent_notification" in TOOL_META_REGISTRY


def test_tool_count_includes_new_tools():
    """Tool count should be 67 (65 baseline + 2 new)."""
    from edu_cloud.ai.engine.tools import collect_all_tools
    all_tools = collect_all_tools()
    assert len(all_tools) >= 67


def test_assign_remedial_homework_in_collect():
    """assign_remedial_homework appears in collect_all_tools()."""
    from edu_cloud.ai.engine.tools import collect_all_tools
    names = [getattr(fn, "_edu_meta", None).name for fn in collect_all_tools() if getattr(fn, "_edu_meta", None)]
    assert "assign_remedial_homework" in names


def test_draft_parent_notification_in_collect():
    """draft_parent_notification appears in collect_all_tools()."""
    from edu_cloud.ai.engine.tools import collect_all_tools
    names = [getattr(fn, "_edu_meta", None).name for fn in collect_all_tools() if getattr(fn, "_edu_meta", None)]
    assert "draft_parent_notification" in names
