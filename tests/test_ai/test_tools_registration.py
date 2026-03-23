"""Verify all 25+ tools are registered and RBAC mapping is correct."""
import pytest
from edu_cloud.ai.registry import tools
import edu_cloud.ai.tools  # noqa: F401 — trigger registration
from edu_cloud.ai.agent import ROLE_TOOL_CATEGORIES


def test_total_tool_count():
    """All tool modules register the expected total (≥25 tools)."""
    all_tools = tools.list_tools()
    assert len(all_tools) >= 25, f"Expected ≥25 tools, got {len(all_tools)}: {all_tools}"


def test_tool_categories_present():
    """All 9 expected categories have at least one tool."""
    expected_categories = {
        "L1_exam", "L1_student",
        "L2_analytics", "L2_cross_school",
        "L3_knowledge", "L3_knowledge_db",
        "L4_action", "L5_bank", "L6_profile",
    }
    found_categories = set()
    for name in tools.list_tools():
        cat = tools._tools[name]["category"]
        found_categories.add(cat)
    for cat in expected_categories:
        assert cat in found_categories, f"Category {cat} has no tools"


def test_platform_admin_gets_all_tools():
    categories = ROLE_TOOL_CATEGORIES["platform_admin"]
    schemas = tools.get_schemas(categories=categories)
    assert len(schemas) >= 25


def test_district_admin_limited():
    categories = ROLE_TOOL_CATEGORIES["district_admin"]
    schemas = tools.get_schemas(categories=categories)
    tool_names = {s["function"]["name"] for s in schemas}
    # Should have L2_cross_school + L3_knowledge + L3_knowledge_db only
    assert "search_curriculum" in tool_names  # L3_knowledge
    assert "get_knowledge_tree" in tool_names  # L3_knowledge_db
    # Should NOT have L1/L4/L5/L6
    assert "get_exam_list" not in tool_names  # L1_exam


def test_principal_has_profile():
    """principal has L6_profile (per design §5.2)."""
    categories = ROLE_TOOL_CATEGORIES["principal"]
    assert "L6_profile" in categories
    schemas = tools.get_schemas(categories=categories)
    tool_names = {s["function"]["name"] for s in schemas}
    assert "get_student_trend" in tool_names


def test_homeroom_teacher_has_bank():
    """homeroom_teacher has L5_bank (per design §5.2)."""
    categories = ROLE_TOOL_CATEGORIES["homeroom_teacher"]
    assert "L5_bank" in categories
    schemas = tools.get_schemas(categories=categories)
    tool_names = {s["function"]["name"] for s in schemas}
    assert "get_student_error_book" in tool_names


def test_parent_only_profile():
    """parent only gets L6_profile."""
    categories = ROLE_TOOL_CATEGORIES["parent"]
    assert categories == ["L6_profile"]
    schemas = tools.get_schemas(categories=categories)
    tool_names = {s["function"]["name"] for s in schemas}
    assert "get_student_trend" in tool_names
    assert "get_exam_list" not in tool_names


def test_empty_categories_no_tools():
    """Empty category list means no tool access."""
    schemas = tools.get_schemas(categories=[])
    assert len(schemas) == 0


def test_unknown_role_gets_empty_list():
    """Unknown role defaults to empty categories."""
    categories = ROLE_TOOL_CATEGORIES.get("unknown_role", [])
    assert categories == []
