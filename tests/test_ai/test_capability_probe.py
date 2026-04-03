import pytest
from unittest.mock import AsyncMock
from edu_cloud.ai.capability_probe import CapabilityProbe, LoopStrategy
from edu_cloud.ai.llm_adapter import LLMProxyAdapter, LLMResponse, TokenUsage
from edu_cloud.ai.schemas import ToolCall


def test_loop_strategy_tier1():
    s = LoopStrategy.for_tier(1)
    assert s.max_turns == 25
    assert s.parallel_tools is True
    assert s.task_planning is True
    assert s.self_verify is True
    assert s.context_compact is True
    assert s.memory_extract is True


def test_loop_strategy_tier2():
    s = LoopStrategy.for_tier(2)
    assert s.max_turns == 15
    assert s.task_planning is True
    assert s.self_verify is False
    assert s.sub_agents is False


def test_loop_strategy_tier3():
    s = LoopStrategy.for_tier(3)
    assert s.max_turns == 8
    assert s.parallel_tools is False
    assert s.task_planning is False


@pytest.mark.asyncio
async def test_probe_tier1():
    adapter = LLMProxyAdapter(base_url="http://test:8100", slot="primary", context_window=200_000)
    adapter.chat = AsyncMock(return_value=LLMResponse(
        tool_calls=[ToolCall(id="t1", name="test_tool", arguments={"x": 1}, _raw={})],
        usage=TokenUsage(10, 5),
        stop_reason="tool_use",
    ))
    probe = CapabilityProbe()
    tier = await probe.determine_tier(adapter)
    assert tier == 1


@pytest.mark.asyncio
async def test_probe_tier2():
    adapter = LLMProxyAdapter(base_url="http://test:8100", slot="primary", context_window=64_000)
    adapter.chat = AsyncMock(return_value=LLMResponse(
        tool_calls=[ToolCall(id="t1", name="test_tool", arguments={"x": 1}, _raw={})],
        usage=TokenUsage(10, 5),
        stop_reason="tool_use",
    ))
    probe = CapabilityProbe()
    tier = await probe.determine_tier(adapter)
    assert tier == 2


@pytest.mark.asyncio
async def test_probe_tier3_no_tool_use():
    adapter = LLMProxyAdapter(base_url="http://test:8100", slot="primary", context_window=8_000)
    adapter.chat = AsyncMock(return_value=LLMResponse(
        content="I cannot use tools",
        usage=TokenUsage(10, 5),
        stop_reason="end_turn",
    ))
    probe = CapabilityProbe()
    tier = await probe.determine_tier(adapter)
    assert tier == 3


@pytest.mark.asyncio
async def test_probe_tier3_on_error():
    adapter = LLMProxyAdapter(base_url="http://test:8100", slot="primary")
    adapter.chat = AsyncMock(side_effect=Exception("connection refused"))
    probe = CapabilityProbe()
    tier = await probe.determine_tier(adapter)
    assert tier == 3


def test_probe_manual_override():
    probe = CapabilityProbe()
    probe.set_override(2)
    assert probe.get_tier() == 2
