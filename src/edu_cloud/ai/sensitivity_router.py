"""Dual-channel LLM routing based on data sensitivity (Design §5)."""
from __future__ import annotations

import logging
from typing import Protocol

from edu_cloud.ai.llm_adapter import LLMProxyAdapter
from edu_cloud.ai.registry import ToolSpec

logger = logging.getLogger(__name__)

_SENSITIVITY_ORDER = {"public": 0, "school": 1, "student": 2}


class HasChannel(Protocol):
    channel: str


class SensitivityRouter:
    """Routes LLM calls to primary (domestic) or enhanced (premium) channel.

    Safety rule: once a student-sensitivity tool has been executed in the session,
    the channel is locked to primary for the remainder of the session.
    """

    def __init__(self, primary: LLMProxyAdapter, enhanced: LLMProxyAdapter | None):
        self.primary = primary
        self.enhanced = enhanced

    def route(self, state: HasChannel, tool_specs: list[ToolSpec]) -> LLMProxyAdapter:
        if self.enhanced is None:
            return self.primary

        if state.channel == "primary_locked":
            return self.primary

        if not tool_specs:
            return self.enhanced

        max_sensitivity = max(_SENSITIVITY_ORDER.get(s.sensitivity, 1) for s in tool_specs)
        if max_sensitivity == 0:  # all public
            return self.enhanced

        return self.primary

    def on_tool_executed(self, state: HasChannel, spec: ToolSpec) -> None:
        if spec.sensitivity == "student":
            state.channel = "primary_locked"
            logger.info("Channel locked to primary after student-sensitivity tool: %s", spec.name)
