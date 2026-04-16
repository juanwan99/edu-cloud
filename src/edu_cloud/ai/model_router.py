"""ModelRouter: zero-token rule-based model selection."""
from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class ModelChoice:
    slots: list[Any]
    tier: str  # "standard" | "advanced"


_DEFAULT_ENHANCE_KEYWORDS = [
    "分析", "报告", "对比", "趋势", "诊断", "评估",
    "预测", "建议", "规划", "总结", "深度",
]


class ModelRouter:
    """Select user (standard) vs system (advanced) model by keyword rules."""

    def __init__(self, enhance_keywords: list[str] | None = None):
        from edu_cloud.config import settings
        if enhance_keywords is not None:
            self._keywords = enhance_keywords
        elif settings.MODEL_ROUTER_ADVANCED_KEYWORDS is not None:
            self._keywords = settings.MODEL_ROUTER_ADVANCED_KEYWORDS
        else:
            self._keywords = _DEFAULT_ENHANCE_KEYWORDS
        logger.info("ModelRouter: %d enhance keywords active", len(self._keywords))

    def route(
        self,
        message: str,
        user_slots: list[Any],
        system_slots: list[Any],
        enhanced_enabled: bool = False,
    ) -> ModelChoice:
        if not user_slots and not system_slots:
            raise ValueError("无可用模型")

        if not enhanced_enabled or not system_slots:
            return ModelChoice(slots=user_slots or system_slots, tier="standard")

        if self._needs_enhancement(message):
            return ModelChoice(slots=system_slots, tier="advanced")

        return ModelChoice(slots=user_slots or system_slots, tier="standard")

    def _needs_enhancement(self, message: str) -> bool:
        if not message:
            return False
        return any(kw in message for kw in self._keywords)
