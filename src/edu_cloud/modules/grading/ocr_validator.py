"""Validate and clean OCR output before grading.

Filters garbage, detects blank answers, and recovers from common OCR failures.
"""
import re


def validate_ocr_blanks(blanks: list[dict]) -> list[dict]:
    """Validate and clean a list of OCR blanks.

    Filters out garbage entries, normalizes text, and marks suspicious results.
    Returns cleaned list (same structure, cleaned text).
    """
    if not blanks:
        return []

    cleaned = []
    for blank in blanks:
        text = blank.get("text", "")
        text = _clean_text(text)

        # Skip if the OCR returned English commentary instead of student answer
        if _is_english_commentary(text):
            blank = {**blank, "text": "（未作答）"}
        else:
            blank = {**blank, "text": text}

        cleaned.append(blank)

    return cleaned


def is_blank_answer(text: str) -> bool:
    """Check if OCR text indicates a blank/unanswered question."""
    if not text or not text.strip():
        return True
    normalized = text.strip()
    blank_markers = {"（未作答）", "（无法辨识）", "[空]", "[?]", ""}
    return normalized in blank_markers


def _clean_text(text: str) -> str:
    """Normalize OCR text: strip whitespace, remove common artifacts."""
    if not text:
        return ""
    text = text.strip()
    # Remove common OCR artifacts
    text = re.sub(r'\s+', ' ', text)  # collapse whitespace
    return text


def _is_english_commentary(text: str) -> bool:
    """Detect if text is LLM English commentary rather than student answer.

    Some LLMs output English explanations like "The student wrote..." or
    "I cannot read this" instead of the actual OCR content.
    """
    if not text:
        return False
    # If > 80% ASCII and contains common LLM commentary patterns
    ascii_ratio = sum(1 for c in text if ord(c) < 128) / max(len(text), 1)
    if ascii_ratio < 0.8:
        return False
    commentary_patterns = [
        r"(?i)the student",
        r"(?i)i cannot",
        r"(?i)unable to",
        r"(?i)this (image|answer|response)",
        r"(?i)no (text|answer|content|writing)",
        r"(?i)blank",
        r"(?i)empty",
    ]
    return any(re.search(p, text) for p in commentary_patterns)


def recover_truncated_blanks(
    blanks: list[dict],
    expected_count: int,
) -> list[dict]:
    """Pad blanks list to expected count if OCR truncated.

    If OCR returned fewer blanks than expected (e.g., 3 of 5),
    pad with empty entries so downstream grading gets the right count.
    """
    if len(blanks) >= expected_count:
        return blanks

    existing_nos = {b.get("blankNo", "") for b in blanks}
    result = list(blanks)

    for i in range(len(blanks) + 1, expected_count + 1):
        blank_no = f"1-{i}"
        if blank_no not in existing_nos:
            result.append({
                "blankNo": blank_no,
                "subQ": "(1)",
                "text": "（未作答）",
            })

    return result
