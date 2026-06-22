"""Tests for AI tool module_code governance."""
from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT / "scripts" / "governance"))

from check_ai_tool_modules import (  # noqa: E402
    build_snapshot,
    check_baseline,
    compare,
    invalid_tools,
    load_baseline,
    scan_tools,
    semantic_mismatches,
    write_baseline,
)


def _school_settings(repo: Path) -> None:
    path = repo / "src/edu_cloud/models"
    path.mkdir(parents=True, exist_ok=True)
    (path / "school_settings.py").write_text(
        """
MODULE_CODES = {
    "exam": "考试管理",
    "homework": "作业管理",
}
""",
        encoding="utf-8",
    )


def _tool(
    repo: Path,
    name: str,
    module_code: str | None,
    domain: str = "exam",
    *,
    requires_modules: str = "",
) -> Path:
    path = repo / "src/edu_cloud/ai/engine/tools/sample.py"
    path.parent.mkdir(parents=True, exist_ok=True)
    module_literal = "None" if module_code is None else f'"{module_code}"'
    requires_arg = f", requires_modules={requires_modules}" if requires_modules else ""
    path.write_text(
        f"""
from edu_cloud.ai.engine.tool_wrapper import edu_tool


@edu_tool(name="{name}", module_code={module_literal}, domain="{domain}"{requires_arg})
def {name}():
    return {{}}
""",
        encoding="utf-8",
    )
    return path


def test_scan_tools_detects_edu_tool_metadata(tmp_path):
    _school_settings(tmp_path)
    _tool(tmp_path, "get_exam_list", "exam", "exam")

    tools = scan_tools(tmp_path)

    assert len(tools) == 1
    assert tools[0].name == "get_exam_list"
    assert tools[0].module_code == "exam"
    assert tools[0].domain == "exam"
    assert tools[0].requires_modules == ()


def test_invalid_module_code_is_reported(tmp_path):
    _school_settings(tmp_path)
    _tool(tmp_path, "bad_tool", "unknown", "exam")

    snapshot = build_snapshot(tmp_path)

    assert [item["name"] for item in invalid_tools(snapshot)] == ["bad_tool"]


def test_base_module_code_none_is_allowed(tmp_path):
    _school_settings(tmp_path)
    _tool(tmp_path, "get_class_roster", None, "student")

    snapshot = build_snapshot(tmp_path)

    assert snapshot["tools"][0]["module_code"] is None
    assert invalid_tools(snapshot) == []
    write_baseline(tmp_path)
    assert check_baseline(tmp_path) == 0


def test_invalid_requires_modules_is_reported(tmp_path):
    _school_settings(tmp_path)
    _tool(
        tmp_path,
        "generate_report",
        "exam",
        "action",
        requires_modules='frozenset({"ghost"})',
    )

    snapshot = build_snapshot(tmp_path)

    invalid = invalid_tools(snapshot)
    assert [item["name"] for item in invalid] == ["generate_report"]
    assert "requires_modules contains 'ghost'" in invalid[0]["_invalid_reasons"]


def test_write_baseline_and_check_clean(tmp_path):
    _school_settings(tmp_path)
    _tool(tmp_path, "get_exam_list", "exam", "exam")
    write_baseline(tmp_path)

    assert check_baseline(tmp_path) == 0


def test_new_tool_fails_against_baseline(tmp_path):
    _school_settings(tmp_path)
    _tool(tmp_path, "get_exam_list", "exam", "exam")
    baseline = build_snapshot(tmp_path)
    write_baseline(tmp_path)

    _tool(tmp_path, "get_homework_stats", "homework", "homework")
    current = build_snapshot(tmp_path)
    diff = compare(current, baseline)

    assert (
        "get_homework_stats",
        "homework",
        "homework",
        "src/edu_cloud/ai/engine/tools/sample.py",
        (),
    ) in diff["new_tools"]
    assert check_baseline(tmp_path) == 1


def test_requires_modules_drift_fails_against_baseline(tmp_path):
    _school_settings(tmp_path)
    _tool(tmp_path, "generate_report", "exam", "action")
    write_baseline(tmp_path)

    _tool(
        tmp_path,
        "generate_report",
        "exam",
        "action",
        requires_modules='frozenset({"homework"})',
    )
    current = build_snapshot(tmp_path)
    baseline = load_baseline(tmp_path / "docs/governance/ai-tool-module-codes.yaml")
    diff = compare(current, baseline)

    assert (
        "generate_report",
        "exam",
        "action",
        "src/edu_cloud/ai/engine/tools/sample.py",
        ("homework",),
    ) in diff["new_tools"]
    assert check_baseline(tmp_path) == 1


def test_semantic_domain_mismatch_is_reported(tmp_path):
    _school_settings(tmp_path)
    _tool(tmp_path, "get_exam_summary", "exam", "analytics")

    snapshot = build_snapshot(tmp_path)

    mismatches = semantic_mismatches(snapshot)
    assert len(mismatches) == 1
    assert mismatches[0]["name"] == "get_exam_summary"
    assert mismatches[0]["expected_module_code"] == "study_analytics"
