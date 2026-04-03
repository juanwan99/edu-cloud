import pytest
from edu_cloud.ai.sensitivity_router import SensitivityRouter
from edu_cloud.ai.llm_adapter import LLMProxyAdapter
from edu_cloud.ai.registry import ToolSpec
from edu_cloud.ai.schemas import Message
from edu_cloud.ai.tool_context import ToolContext, ToolResult
from dataclasses import dataclass


@dataclass
class FakeState:
    channel: str = "primary"


def _make_spec(name, sensitivity="school"):
    async def _noop(i, c):
        return ToolResult(success=True, data=None)
    return ToolSpec(name=name, description="", parameters={}, func=_noop, sensitivity=sensitivity, is_read_only=True)


def test_no_enhanced_channel():
    primary = LLMProxyAdapter(base_url="http://test:8100", slot="primary")
    router = SensitivityRouter(primary=primary, enhanced=None)
    state = FakeState()
    result = router.route(state, [_make_spec("t1", "public")])
    assert result is primary


def test_public_tools_use_enhanced():
    primary = LLMProxyAdapter(base_url="http://test:8100", slot="primary")
    enhanced = LLMProxyAdapter(base_url="http://test:8100", slot="enhanced")
    router = SensitivityRouter(primary=primary, enhanced=enhanced)
    state = FakeState()
    result = router.route(state, [_make_spec("t1", "public"), _make_spec("t2", "public")])
    assert result is enhanced


def test_school_tools_use_primary():
    primary = LLMProxyAdapter(base_url="http://test:8100", slot="primary")
    enhanced = LLMProxyAdapter(base_url="http://test:8100", slot="enhanced")
    router = SensitivityRouter(primary=primary, enhanced=enhanced)
    state = FakeState()
    result = router.route(state, [_make_spec("t1", "school")])
    assert result is primary


def test_student_tool_locks_channel():
    primary = LLMProxyAdapter(base_url="http://test:8100", slot="primary")
    enhanced = LLMProxyAdapter(base_url="http://test:8100", slot="enhanced")
    router = SensitivityRouter(primary=primary, enhanced=enhanced)
    state = FakeState()
    router.on_tool_executed(state, _make_spec("t1", "student"))
    assert state.channel == "primary_locked"

    # Even all-public tools now route to primary
    result = router.route(state, [_make_spec("t2", "public")])
    assert result is primary


def test_empty_tools_use_enhanced():
    primary = LLMProxyAdapter(base_url="http://test:8100", slot="primary")
    enhanced = LLMProxyAdapter(base_url="http://test:8100", slot="enhanced")
    router = SensitivityRouter(primary=primary, enhanced=enhanced)
    state = FakeState()
    result = router.route(state, [])
    assert result is enhanced
