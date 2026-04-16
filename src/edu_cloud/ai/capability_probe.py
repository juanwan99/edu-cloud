"""Detect LLM model capabilities and select agent loop tier (Design S5)."""
from __future__ import annotations

import logging
from dataclasses import dataclass

from edu_cloud.ai.llm_adapter import LLMProxyAdapter, LLMRequest
from edu_cloud.ai.schemas import Message

logger = logging.getLogger(__name__)

@dataclass(frozen=True)
class LoopStrategy:
    tier: int
    max_turns: int
    parallel_tools: bool
    task_planning: bool
    self_verify: bool
    sub_agents: bool
    context_compact: bool
    memory_extract: bool

    @classmethod
    def for_tier(cls, tier: int) -> LoopStrategy:
        if tier == 1:
            return cls(tier=1, max_turns=25, parallel_tools=True, task_planning=True,
                       self_verify=True, sub_agents=True, context_compact=True, memory_extract=True)
        if tier == 2:
            return cls(tier=2, max_turns=15, parallel_tools=True, task_planning=True,
                       self_verify=False, sub_agents=False, context_compact=True, memory_extract=False)
        return cls(tier=3, max_turns=8, parallel_tools=False, task_planning=False,
                   self_verify=False, sub_agents=False, context_compact=False, memory_extract=False)


class CapabilityProbe:
    def __init__(self, tier_thresholds: list[int] | None = None):
        from edu_cloud.config import settings
        self._tier_thresholds = tier_thresholds or settings.TIER_CONTEXT_THRESHOLDS
        self._override: int | None = None
        self._cached_tier: int | None = None

    def set_override(self, tier: int) -> None:
        self._override = tier
        self._cached_tier = tier

    def get_tier(self) -> int:
        return self._cached_tier or 3

    async def determine_tier(self, adapter: LLMProxyAdapter) -> int:
        if self._override is not None:
            self._cached_tier = self._override
            return self._override

        has_tool_use = await self._test_tool_use(adapter)
        context_window = adapter.context_window_size()

        if has_tool_use and context_window >= self._tier_thresholds[0]:
            tier = 1
        elif has_tool_use and context_window >= self._tier_thresholds[1]:
            tier = 2
        else:
            tier = 3

        self._cached_tier = tier
        adapter.set_capabilities({
            "tool_use": has_tool_use,
            "parallel_tools": has_tool_use and tier in (1, 2),
            "context_window": context_window,
        })
        logger.info("CapabilityProbe: tier=%d, tool_use=%s, context=%d", tier, has_tool_use, context_window)
        return tier

    async def _test_tool_use(self, adapter: LLMProxyAdapter) -> bool:
        try:
            resp = await adapter.chat(LLMRequest(
                messages=[Message(role="user", content="Call test_tool with x=1")],
                tools=[{
                    "type": "function",
                    "function": {
                        "name": "test_tool",
                        "description": "Test tool for capability probing",
                        "parameters": {"type": "object", "properties": {"x": {"type": "integer"}}},
                    },
                }],
                max_tokens=100,
                stream=False,
            ))
            return resp.tool_calls is not None and len(resp.tool_calls) > 0
        except Exception:
            logger.warning("CapabilityProbe: tool_use test failed, assuming no support")
            return False
