"""Grounded generation layer — DataSource provenance + OutputValidator anti-hallucination."""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class DataSource:
    """Immutable provenance record attached to a ToolResult."""

    type: str        # e.g. "db_query", "api_fetch", "knowledge_base"
    table: str       # primary table / endpoint
    ref: str         # human-readable reference (exam name, date range, etc.)
    queried_at: str  # ISO-8601 timestamp

    def to_dict(self) -> dict[str, Any]:
        return {
            "type": self.type,
            "table": self.table,
            "ref": self.ref,
            "queried_at": self.queried_at,
        }


# ---------------------------------------------------------------------------
# OutputValidator — pure regex + numeric comparison, NO LLM calls.
# ---------------------------------------------------------------------------

@dataclass
class ValidationResult:
    status: str  # "pass" | "warn" | "fail"
    ungrounded_values: list[float] = field(default_factory=list)
    contradictions: list[dict] = field(default_factory=list)


@dataclass(frozen=True)
class NumberToken:
    value: float
    unit: str       # "分"/"名"/"人"/"%"/"" etc.
    key_path: str   # "avg_score" / "" (from response text)


# Unit -> tolerance mapping
_TOLERANCE: dict[str, float] = {
    "分": 0.005,   # 0.5% relative
    "名": 0.0,
    "人": 0.0,
    "个": 0.0,
    "次": 0.0,
    "所": 0.0,
    "班": 0.0,
    "科": 0.0,
    "题": 0.0,
    "道": 0.0,
    "%": 0.02,     # 2% relative
}
_DEFAULT_TOLERANCE = 0.05  # 5% for unknown units

_UNIT_LIST = "分|%|人|名|个|次|所|班|科|题|道"
_NUM_PATTERN = re.compile(rf'(\d+\.?\d*)\s*({_UNIT_LIST})')

_RATE_KEYWORDS = {"rate", "ratio", "percent", "及格", "优秀", "pass", "合格"}


class OutputValidator:
    """Post-generation validator: check response numbers against tool data.

    HARD CONSTRAINT: No LLM calls. Pure regex + numeric comparison only.
    """

    def validate(self, response: str, tool_results: list) -> ValidationResult:
        if not tool_results:
            return ValidationResult(status="pass")

        response_tokens = self._extract_number_tokens(response)
        if not response_tokens:
            return ValidationResult(status="pass")

        tool_tokens: list[NumberToken] = []
        for tr in tool_results:
            if tr.data:
                self._collect_number_tokens(tr.data, tool_tokens)

        if not tool_tokens:
            return ValidationResult(status="pass")

        ungrounded: list[float] = []
        contradictions: list[dict] = []

        for rt in response_tokens:
            tolerance = _TOLERANCE.get(rt.unit, _DEFAULT_TOLERANCE)
            # F003 fix: unit-aware matching — % tokens only match % tool tokens
            compatible_values = self._compatible_tool_values(rt, tool_tokens)
            if self._matches_any(rt.value, compatible_values):
                continue
            closest = self._find_closest(rt.value, compatible_values)
            if closest is not None:
                rel_err = abs(rt.value - closest) / max(abs(closest), 1)
                if rel_err <= tolerance:
                    continue  # within tolerance
                contradictions.append({"response": rt.value, "tool": closest, "unit": rt.unit})
            else:
                ungrounded.append(rt.value)

        if contradictions:
            return ValidationResult(status="fail", contradictions=contradictions)
        if ungrounded:
            return ValidationResult(status="warn", ungrounded_values=ungrounded)
        return ValidationResult(status="pass")

    def _extract_number_tokens(self, text: str) -> list[NumberToken]:
        seen: set[tuple[float, str]] = set()
        tokens: list[NumberToken] = []
        for m in _NUM_PATTERN.finditer(text):
            value = float(m.group(1))
            unit = m.group(2)
            key = (value, unit)
            if key not in seen:
                seen.add(key)
                tokens.append(NumberToken(value=value, unit=unit, key_path=""))
        return tokens

    def _collect_number_tokens(
        self,
        data: Any,
        result: list[NumberToken],
        key_path: str = "",
        depth: int = 0,
    ) -> None:
        if depth > 5:
            return
        if isinstance(data, (int, float)):
            result.append(NumberToken(value=float(data), unit="", key_path=key_path))
            # P2-2: conditional percent conversion
            if 0 < data < 1 and any(kw in key_path.lower() for kw in _RATE_KEYWORDS):
                result.append(NumberToken(value=round(data * 100, 2), unit="%", key_path=key_path))
        elif isinstance(data, dict):
            for k, v in data.items():
                child_path = f"{key_path}.{k}" if key_path else k
                self._collect_number_tokens(v, result, key_path=child_path, depth=depth + 1)
        elif isinstance(data, list):
            for item in data:
                self._collect_number_tokens(item, result, key_path=key_path, depth=depth + 1)

    @staticmethod
    def _compatible_tool_values(rt: NumberToken, tool_tokens: list[NumberToken]) -> set[float]:
        """Return tool values compatible with the response token's unit context.

        F003 fix: a response token with unit "%" should only match tool tokens
        that also have unit "%" (from percent conversion). This prevents
        student_count=85 from grounding "85%".
        """
        if rt.unit == "%":
            # % in response → only match tool tokens that are also %
            return {t.value for t in tool_tokens if t.unit == "%"}
        # Non-% response tokens match all tool values (backward compatible)
        return {t.value for t in tool_tokens}

    def _matches_any(self, num: float, tool_values: set[float]) -> bool:
        return any(abs(num - tv) < 0.01 for tv in tool_values)

    def _find_closest(self, num: float, tool_values: set[float]) -> float | None:
        if not tool_values:
            return None
        return min(tool_values, key=lambda x: abs(x - num))
