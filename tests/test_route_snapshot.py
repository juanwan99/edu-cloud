"""Route snapshot — lock down all API paths before registry migration.

Any route loss during migration will cause an immediate FAIL.
ORC-001: All existing API endpoints must remain reachable after migration.
"""
import pytest

from edu_cloud.api.app import create_app

# Every /api/v1/* prefix that currently exists.
# Sorted alphabetically for easy diffing.
EXPECTED_PREFIXES = [
    "/api/v1/academic",
    "/api/v1/ai",
    "/api/v1/analytics",
    "/api/v1/auth",
    "/api/v1/bank",
    "/api/v1/calendar",
    "/api/v1/card",
    "/api/v1/classes",
    "/api/v1/client-logs",
    "/api/v1/conduct",
    "/api/v1/dashboard",
    "/api/v1/exams",
    "/api/v1/grades",
    "/api/v1/grading",
    "/api/v1/health",
    "/api/v1/homework",
    "/api/v1/joint-exams",
    "/api/v1/knowledge",
    "/api/v1/knowledge-tree",
    "/api/v1/llm-config",
    "/api/v1/marking",
    "/api/v1/menus",
    "/api/v1/notifications",
    "/api/v1/pipeline",
    "/api/v1/profile",
    "/api/v1/questions",
    "/api/v1/scan",
    "/api/v1/schools",
    "/api/v1/students",
    "/api/v1/studio",
    "/api/v1/teachers",
    "/api/v1/templates",
    "/api/v1/version",
    "/api/v1/workspace",
]


@pytest.fixture
def app():
    return create_app()


def _collect_prefixes(app) -> set[str]:
    """Walk app.routes and extract 3-segment prefixes (/api/v1/<resource>)."""
    prefixes = set()
    for route in app.routes:
        path = getattr(route, "path", None)
        if not path:
            continue
        parts = path.strip("/").split("/")
        if len(parts) >= 3:
            prefixes.add("/" + "/".join(parts[:3]))
    return prefixes


def test_all_expected_prefixes_registered(app):
    """Every prefix in the snapshot must be present in the running app."""
    registered = _collect_prefixes(app)
    missing = sorted(p for p in EXPECTED_PREFIXES if p not in registered)
    assert not missing, f"Missing route prefixes after migration: {missing}"


def test_no_unexpected_prefix_removal(app):
    """Guard against accidentally removing routes during refactor.

    The total number of registered /api/v1/* prefixes must not drop
    below the snapshot count.
    """
    registered = _collect_prefixes(app)
    api_v1 = {p for p in registered if p.startswith("/api/v1/")}
    assert len(api_v1) >= len(EXPECTED_PREFIXES), (
        f"Route count dropped: expected >= {len(EXPECTED_PREFIXES)}, "
        f"got {len(api_v1)}"
    )
