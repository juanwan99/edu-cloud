"""router_registry unit tests."""
import importlib

import pytest

from edu_cloud.api.router_registry import MODULE_ROUTERS, PLATFORM_ROUTERS, register_all


def test_all_entries_importable():
    """Every registry entry must be importable with the specified attribute."""
    for import_path, attr in PLATFORM_ROUTERS + MODULE_ROUTERS:
        mod = importlib.import_module(import_path)
        router = getattr(mod, attr, None)
        assert router is not None, f"{import_path}.{attr} not found"


def test_all_routers_have_prefix():
    """Every router must declare a prefix (not relying on app-level override)."""
    for import_path, attr in PLATFORM_ROUTERS + MODULE_ROUTERS:
        mod = importlib.import_module(import_path)
        router = getattr(mod, attr)
        assert router.prefix, f"{import_path}.{attr} has no prefix"


def test_no_duplicate_entry():
    """The same (import_path, attr) pair must not appear twice in the registry.

    Note: multiple routers may share a prefix (e.g. school sub-routers all
    use /api/v1/schools/{school_id}, grading sub-routers share /api/v1/grading).
    This is a normal FastAPI pattern. We only guard against accidentally
    registering the exact same router object twice.
    """
    entries = PLATFORM_ROUTERS + MODULE_ROUTERS
    seen: dict[tuple[str, str], int] = {}
    for idx, (import_path, attr) in enumerate(entries):
        key = (import_path, attr)
        if key in seen:
            pytest.fail(
                f"Duplicate registry entry at index {seen[key]} and {idx}: "
                f"{import_path}.{attr}"
            )
        seen[key] = idx


def test_register_all_attaches_routers():
    """register_all should attach all routers to the app."""
    from edu_cloud.api.app import create_app

    app = create_app()
    # Collect all registered route prefixes from the app
    registered_paths = set()
    for route in app.routes:
        if hasattr(route, "path"):
            registered_paths.add(route.path)

    for import_path, attr in MODULE_ROUTERS:
        mod = importlib.import_module(import_path)
        router = getattr(mod, attr)
        prefix = router.prefix
        # At least one route in app must start with this router's prefix
        has_route = any(p.startswith(prefix) for p in registered_paths)
        assert has_route, (
            f"{import_path}.{attr} prefix '{prefix}' has no matching routes in app"
        )
