"""Shared ordering helpers for exam questions."""
from __future__ import annotations

import re
from typing import Any

_QUESTION_NUMBER_RE = re.compile(r"\s*(\d+)")


def question_sort_key(question: Any) -> tuple[int, int, str]:
    """Sort by the leading question number; non-numeric names go last."""
    if isinstance(question, dict):
        name = question.get("name") or question.get("question_name") or question.get("qno") or ""
    else:
        name = getattr(question, "name", "") or ""
    text = str(name)
    match = _QUESTION_NUMBER_RE.match(text)
    if match:
        return (0, int(match.group(1)), text)
    return (1, 0, text)
