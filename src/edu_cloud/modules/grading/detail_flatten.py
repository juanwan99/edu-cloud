"""将 LLM 返回的嵌套 details 结构展平为前端可渲染的扁平格式。

LLM 按 zhixue prompt 格式返回:
  [{subQuestion: "6-1", score: 1, fullScore: 1, blanks: [{index, answer, score, fullScore, correct, reason}]}]

前端期望:
  [{blankNo: "6-1", score: 1, maxScore: 1, reason: "...", answer: "...", correct: true}]
"""
from __future__ import annotations

import json
import re

_REASON_PATTERNS = [
    (re.compile(r"满足\s*judgingRules\s*中\s*"), "满足评分标准中"),
    (re.compile(r"命中\s*judgingRules\s*中\s*"), "命中评分标准中"),
    (re.compile(r"judgingRules\s*中\s*"), "评分标准中"),
    (re.compile(r"judgingRules"), "评分标准"),
]


def sanitize_reason(reason: str) -> str:
    if not reason:
        return reason
    for pattern, replacement in _REASON_PATTERNS:
        reason = pattern.sub(replacement, reason)
    return reason


def parse_raw_content(raw_content: str) -> dict | None:
    """解析 LLM raw_content（可能被 markdown 代码块包裹）。"""
    if not raw_content:
        return None
    text = raw_content.strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[1] if "\n" in text else text[3:]
        if text.endswith("```"):
            text = text[:-3].rstrip()
    try:
        parsed = json.loads(text)
        return parsed if isinstance(parsed, dict) else None
    except (json.JSONDecodeError, TypeError):
        return None


def extract_details_from_raw(raw_content: str) -> list | None:
    """从 raw_content 字符串中提取 details 列表。"""
    parsed = parse_raw_content(raw_content)
    if parsed:
        return parsed.get("details")
    return None


def flatten_llm_details(details: list | None) -> list:
    if not details or not isinstance(details, list):
        return []

    first = details[0]
    if not isinstance(first, dict):
        return details

    if "blankNo" in first and "blanks" not in first:
        for d in details:
            if isinstance(d, dict) and "reason" in d:
                d["reason"] = sanitize_reason(d["reason"])
        return details

    if "subQuestion" not in first and "blanks" not in first:
        return details

    flat: list[dict] = []
    for item in details:
        if not isinstance(item, dict):
            continue
        sub_q = item.get("subQuestion", "")
        blanks = item.get("blanks")
        if blanks and isinstance(blanks, list):
            for blank in blanks:
                if not isinstance(blank, dict):
                    continue
                blank_no = sub_q
                if len(blanks) > 1:
                    blank_no = f"{sub_q}-{blank.get('index', '')}"
                flat.append({
                    "blankNo": str(blank_no),
                    "score": blank.get("score", 0),
                    "maxScore": blank.get("fullScore", blank.get("maxScore", 0)),
                    "reason": sanitize_reason(blank.get("reason", "")),
                    "answer": blank.get("answer", ""),
                    "correct": blank.get("correct", False),
                })
        else:
            flat.append({
                "blankNo": str(sub_q),
                "score": item.get("score", 0),
                "maxScore": item.get("fullScore", item.get("maxScore", 0)),
                "reason": sanitize_reason(item.get("reason", "")),
                "answer": item.get("answer", ""),
                "correct": item.get("correct", False),
            })
    return flat if flat else details
