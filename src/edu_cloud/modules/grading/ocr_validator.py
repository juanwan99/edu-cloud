"""Validate and clean OCR output before grading.

Filters garbage, detects blank answers, and recovers from common OCR failures.
"""
import re

_DOMAIN_OCR_FIXES = {
    "受精精": "受精",
    "间隔隔": "间隔",
}
UNANSWERED_TEXT = "（未作答）"
OCR_REVIEW_TEXT = "（无法辨识，需人工复核）"


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

        if _is_english_commentary(text):
            blank = _mark_ocr_review_needed(
                blank,
                reason="ocr_english_commentary",
            )
        else:
            blank = {**blank, "text": text}

        cleaned.append(blank)

    return cleaned


def is_blank_answer(text: str) -> bool:
    """Check if OCR text indicates a blank/unanswered question."""
    if not text or not text.strip():
        return True
    normalized = text.strip()
    blank_markers = {UNANSWERED_TEXT, "[空]", "[?]", ""}
    return normalized in blank_markers


def _clean_text(text: str) -> str:
    """Normalize OCR text: strip whitespace, remove common artifacts."""
    if not text:
        return ""
    text = text.strip()
    text = re.sub(r'\s+', ' ', text)
    for old, new in _DOMAIN_OCR_FIXES.items():
        text = text.replace(old, new)
    return text


def _is_english_commentary(text: str) -> bool:
    """Detect if text is LLM English commentary rather than student answer."""
    if not text:
        return False
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
    expected_count: int | list[dict],
) -> list[dict]:
    """Pad blanks list to expected count if OCR truncated.

    expected_count can be an int or the criteria list (to get proper blankNo/subQ).
    """
    if isinstance(expected_count, list):
        criteria = expected_count
        expected_n = len(criteria)
    else:
        criteria = None
        expected_n = int(expected_count)

    if len(blanks) >= expected_n:
        return blanks

    existing_nos = {b.get("blankNo", "") for b in blanks}
    result = list(blanks)

    for i in range(len(blanks), expected_n):
        if criteria:
            blank_no = str(criteria[i].get("blankNo", f"1-{i + 1}"))
            sub_q = criteria[i].get("subQ", "(1)")
        else:
            blank_no = f"1-{i + 1}"
            sub_q = "(1)"
        if blank_no not in existing_nos:
            result.append({
                "blankNo": blank_no,
                "subQ": sub_q,
                "text": OCR_REVIEW_TEXT,
                "needs_review": True,
                "ocr_status": "needs_review",
                "review_reason": "ocr_missing_blank",
            })

    return result


def _mark_ocr_review_needed(blank: dict, *, reason: str) -> dict:
    return {
        **blank,
        "text": OCR_REVIEW_TEXT,
        "needs_review": True,
        "ocr_status": "needs_review",
        "review_reason": reason,
    }
