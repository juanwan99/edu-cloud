"""Robust JSON extraction from LLM responses.

5-level fallback:
  1. clean parse
  2. code block strip
  3. bracket balance
  4. greedy search (progressively shorter substrings)
  5. truncation repair (close open brackets/braces)

Ported from zhixue-server llmService.extractJsonFromText.
"""

import json
import re


def extract_json(text: str, *, expected_details_count: int | None = None) -> dict | list | None:
    """Extract JSON object or array from LLM response text.

    Tries 5 strategies in order:
    1. Direct json.loads on stripped text
    2. Strip markdown code block fences, then parse
    3. Find balanced bracket pair and parse the substring
    4. Greedy: find first opener, try progressively shorter substrings
    5. Truncation repair: close open brackets/braces

    If expected_details_count is set and the result is a dict with a
    'details' list that has fewer items, returns None (forces retry).
    Returns parsed dict/list, or None if no valid JSON found.
    """
    if not text or not text.strip():
        return None
    text = text.strip()

    # Level 1: direct parse
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # Level 2: strip markdown code block
    stripped = _strip_code_block(text)
    if stripped != text:
        try:
            return json.loads(stripped)
        except json.JSONDecodeError:
            pass

    # Level 3: find balanced brackets
    result = _find_balanced(stripped or text)
    if result is not None:
        return result

    # Level 4: greedy — find first { or [ and try to parse
    result = _greedy_parse(text)
    if result is not None:
        return result

    # Level 5: truncation repair — close open brackets/braces
    result = _repair_truncated(text)
    if result is not None:
        if _is_incomplete(result, expected_details_count):
            return None
        return result

    return None


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
    """Last resort: find first opener and try progressively shorter substrings."""
    for opener in ["{", "["]:
        start = text.find(opener)
        if start == -1:
            continue
        candidate = text[start:]
        # Try progressively shorter substrings
        for end in range(len(candidate), 0, -1):
            try:
                return json.loads(candidate[:end])
            except json.JSONDecodeError:
                continue
    return None


def _repair_truncated(text: str) -> dict | list | None:
    """Attempt to repair truncated JSON by closing open brackets/braces.

    Walks the text from the first opener, tracking the bracket stack.
    At each position that ends a complete key-value pair (after a comma
    or at end-of-input), tries closing all open brackets to form valid JSON.
    Returns the largest valid result found, or None.
    """
    for opener in ["{", "["]:
        start = text.find(opener)
        if start == -1:
            continue
        candidate = text[start:]

        # Track bracket stack to know what closers are needed
        stack: list[str] = []
        in_string = False
        escape = False
        last_good_pos = -1
        closer_map = {"{": "}", "[": "]"}

        for i, ch in enumerate(candidate):
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
            if ch in closer_map:
                stack.append(closer_map[ch])
            elif ch in ("}", "]"):
                if stack and stack[-1] == ch:
                    stack.pop()
            elif ch == "," and stack:
                # After a comma at depth >= 1, we might have a valid truncation point
                last_good_pos = i

        # Try closing at the end of input first, then at last comma
        for pos in [len(candidate), last_good_pos]:
            if pos <= 0:
                continue
            fragment = candidate[:pos].rstrip().rstrip(",")
            # Recompute stack for this fragment
            repair_stack: list[str] = []
            in_str = False
            esc = False
            for ch in fragment:
                if esc:
                    esc = False
                    continue
                if ch == "\\":
                    esc = True
                    continue
                if ch == '"':
                    in_str = not in_str
                    continue
                if in_str:
                    continue
                if ch in closer_map:
                    repair_stack.append(closer_map[ch])
                elif ch in ("}", "]"):
                    if repair_stack and repair_stack[-1] == ch:
                        repair_stack.pop()

            if not repair_stack:
                continue
            # Close all open brackets in reverse order
            repaired = fragment + "".join(reversed(repair_stack))
            try:
                return json.loads(repaired)
            except json.JSONDecodeError:
                continue
    return None


def _is_incomplete(parsed: dict | list, expected_details_count: int | None) -> bool:
    """Check if a parsed grading response is incomplete (truncation artifact)."""
    if expected_details_count is None or not isinstance(parsed, dict):
        return False
    details = parsed.get("details")
    if not isinstance(details, list):
        return False
    if len(details) < expected_details_count:
        return True
    return False
