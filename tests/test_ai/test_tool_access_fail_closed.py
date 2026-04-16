"""Fail-closed capability tests: no record = DENY (D7)."""
import pytest
from unittest.mock import AsyncMock
from edu_cloud.ai.tool_access import ToolAccessResolver
from edu_cloud.ai.registry import ToolSpec


def _make_spec(name, allowed_roles=None, module_code=None, requires_capabilities=None):
    return ToolSpec(
        name=name, description="test", parameters={},
        func=AsyncMock(), category="general",
        module_code=module_code, domain="general",
        allowed_roles=allowed_roles,
        requires_capabilities=requires_capabilities or [],
    )


def test_no_capability_record_rejects():
    """No capability record -> DENY (fail-closed)."""
    spec = _make_spec("tool_x", allowed_roles=["subject_teacher"],
                       requires_capabilities=[("analytics", "read")])
    resolver = ToolAccessResolver()
    result = resolver.resolve([spec], role="subject_teacher",
                               enabled_modules=set(),
                               capabilities={})
    assert len(result) == 0  # fail-closed: no record = deny


def test_module_disabled_rejects():
    spec = _make_spec("tool_y", allowed_roles=["subject_teacher"],
                       module_code="grading")
    result = ToolAccessResolver().resolve([spec], role="subject_teacher",
                                          enabled_modules={"analytics"},
                                          capabilities={})
    assert len(result) == 0


def test_explicit_allow_passes():
    spec = _make_spec("tool_z", allowed_roles=["subject_teacher"],
                       requires_capabilities=[("analytics", "read")])
    result = ToolAccessResolver().resolve([spec], role="subject_teacher",
                                          enabled_modules=set(),
                                          capabilities={("analytics", "read"): True})
    assert len(result) == 1


def test_no_capability_requirement_passes():
    """Tool with empty requires_capabilities -> always passes capability check."""
    spec = _make_spec("tool_w", allowed_roles=["subject_teacher"],
                       requires_capabilities=[])
    result = ToolAccessResolver().resolve([spec], role="subject_teacher",
                                          enabled_modules=set(),
                                          capabilities={})
    assert len(result) == 1


def test_explicit_false_still_rejects():
    """Explicit False -> DENY (unchanged behavior)."""
    spec = _make_spec("tool_a", allowed_roles=["subject_teacher"],
                       requires_capabilities=[("exam", "write")])
    result = ToolAccessResolver().resolve([spec], role="subject_teacher",
                                          enabled_modules=set(),
                                          capabilities={("exam", "write"): False})
    assert len(result) == 0


def test_partial_capability_match_rejects():
    """Tool requires 2 capabilities, only 1 present -> DENY."""
    spec = _make_spec("tool_b", allowed_roles=["subject_teacher"],
                       requires_capabilities=[("exam", "read"), ("grading", "write")])
    result = ToolAccessResolver().resolve([spec], role="subject_teacher",
                                          enabled_modules=set(),
                                          capabilities={("exam", "read"): True})
    # grading.write has no record -> fail-closed -> deny
    assert len(result) == 0


def test_all_capabilities_explicit_true_passes():
    """All required capabilities explicitly True -> ALLOW."""
    spec = _make_spec("tool_c", allowed_roles=["subject_teacher"],
                       requires_capabilities=[("exam", "read"), ("grading", "write")])
    result = ToolAccessResolver().resolve([spec], role="subject_teacher",
                                          enabled_modules=set(),
                                          capabilities={("exam", "read"): True,
                                                        ("grading", "write"): True})
    assert len(result) == 1
