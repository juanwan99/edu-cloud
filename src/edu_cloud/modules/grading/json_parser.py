"""Robust JSON extraction from LLM responses.

4-level fallback:
  1. clean parse
  2. code block strip
  3. bracket balance
  4. greedy search for complete JSON substrings

Truncated JSON is intentionally not repaired. In grading, returning a partial
result is worse than forcing the caller to retry or fail visibly.
"""

import json
import re


def extract_json(
    text: str,
    *,
    expected_details_count: int | None = None,
) -> dict | list | None:
    """Extract a complete JSON object or array from LLM response text.

    If expected_details_count is set and a parsed dict has a shorter details
    list, return None so the caller can retry instead of accepting partial
    grading output.
    """
    if not text or not text.strip():
        return None
    text = text.strip()

    for candidate in _json_candidates(text):
        try:
            return _complete_or_none(json.loads(candidate), expected_details_count)
        except json.JSONDecodeError:
            continue

    result = _find_balanced(_strip_code_block(text))
    if result is not None:
        return _complete_or_none(result, expected_details_count)

    result = _greedy_parse(text)
    if result is not None:
        return _complete_or_none(result, expected_details_count)

    return None


def _json_candidates(text: str):
    yield text
    stripped = _strip_code_block(text)
    if stripped != text:
        yield stripped


def _strip_code_block(text: str) -> str:
    """Remove markdown code block fences (```json ... ``` or ``` ... ```)."""
    m = re.match(r"```(?:json)?\s*\n?(.*?)```", text, re.DOTALL)
    if m:
        return m.group(1).strip()
    return text


def _find_balanced(text: str) -> dict | list | None:
    """Find a balanced JSON object or array by tracking bracket depth."""
    for opener, closer in [("{", "}"), ("[", "]")]:
        start = text.find(opener)
        if start == -1:
            continue
        depth = 0
        in_string = False
        escape = False
        for i in range(start, len(text)):
            ch = text[i]
            if escape:
                escape = False
                continue
            if ch == "\\":
                escape = True
                continue
            if ch == '"':
                in_string = not in_string
                continue
            if in_string:
                continue
            if ch == opener:
                depth += 1
            elif ch == closer:
                depth -= 1
                if depth == 0:
                    try:
                        return json.loads(text[start : i + 1])
                    except json.JSONDecodeError:
                        break
    return None


def _greedy_parse(text: str) -> dict | list | None:
    """Find the first opener and try progressively shorter complete substrings."""
    for opener in ["{", "["]:
        start = text.find(opener)
        if start == -1:
            continue
        candidate = text[start:]
        for end in range(len(candidate), 0, -1):
            try:
                return json.loads(candidate[:end])
            except json.JSONDecodeError:
                continue
    return None


def _is_incomplete(parsed: dict | list, expected_details_count: int | None) -> bool:
    """Check if a parsed grading response is incomplete."""
    if expected_details_count is None or not isinstance(parsed, dict):
        return False
    details = parsed.get("details")
    if not isinstance(details, list):
        return False
    return len(details) < expected_details_count


def _complete_or_none(
    parsed: dict | list,
    expected_details_count: int | None,
) -> dict | list | None:
    if _is_incomplete(parsed, expected_details_count):
        return None
    return parsed
