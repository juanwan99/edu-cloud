"""Governance tests for future portal aggregation boundaries."""
from __future__ import annotations

from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
CONTRACT = PROJECT_ROOT / "docs/governance/portal-aggregation-contract.md"


def test_portal_contract_defines_aggregation_dtos():
    text = CONTRACT.read_text(encoding="utf-8")

    for term in (
        "TodoItem",
        "MessageItem",
        "CalendarDigestItem",
        "ServiceEntry",
        "source_module",
        "source_type",
        "source_id",
        "action_url",
        "permission",
        "module_code",
        "assignee_scope",
    ):
        assert term in text

    for endpoint in (
        "GET /api/v1/portal/summary",
        "GET /api/v1/portal/todos",
        "GET /api/v1/portal/messages",
        "GET /api/v1/portal/calendar-digest",
        "GET /api/v1/portal/services",
    ):
        assert endpoint in text


def test_future_portal_code_does_not_import_source_tables_directly():
    future_paths = [
        PROJECT_ROOT / "src/edu_cloud/modules/portal",
        PROJECT_ROOT / "src/edu_cloud/api/portal.py",
        PROJECT_ROOT / "src/edu_cloud/api/portal",
    ]
    forbidden = {
        "from edu_cloud.models.notification import Notification",
        "from edu_cloud.models.calendar import CalendarEvent",
        "from edu_cloud.models.calendar import NotificationRule",
        "from edu_cloud.models.approval import ApprovalFlow",
        "from edu_cloud.models.approval import ApprovalStep",
        "from edu_cloud.models.workflow import WorkflowRun",
        "from edu_cloud.models.workflow import WorkflowStep",
    }

    violations: list[str] = []
    for path in future_paths:
        if path.is_file():
            files = [path]
        elif path.is_dir():
            files = sorted(path.rglob("*.py"))
        else:
            continue
        for file in files:
            content = file.read_text(encoding="utf-8")
            for needle in forbidden:
                if needle in content:
                    violations.append(f"{file.relative_to(PROJECT_ROOT)} imports {needle}")

    assert not violations
