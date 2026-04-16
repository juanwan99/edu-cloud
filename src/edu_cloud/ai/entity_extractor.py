"""Extract entities (subject, class, student) from Chinese text using regex."""
from __future__ import annotations

import re


class EntityExtractor:
    SUBJECT_MAP = {
        "语文": "chinese",
        "数学": "math",
        "英语": "english",
        "物理": "physics",
        "化学": "chemistry",
        "生物": "biology",
        "历史": "history",
        "地理": "geography",
        "政治": "politics",
    }
    CLASS_PATTERN = re.compile(r"(\d+)\s*班")
    # Strategy: try exact 2-char match first (most Chinese names), then 3-char.
    # Exact quantifiers prevent the regex from over-capturing preceding context.
    _STUDENT_2 = re.compile(r"([\u4e00-\u9fa5]{2})(?:同学|的)")
    _STUDENT_3 = re.compile(r"([\u4e00-\u9fa5]{3})(?:同学)")

    @classmethod
    def extract(cls, message: str) -> dict:
        result: dict[str, str] = {}
        for cn, en in cls.SUBJECT_MAP.items():
            if cn in message:
                result["subject"] = en
                break
        m = cls.CLASS_PATTERN.search(message)
        if m:
            result["class_ref"] = m.group(1)
        # Try 2-char first (most common: 小明同学/张三的), then 3-char (王小明同学)
        m = cls._STUDENT_2.search(message) or cls._STUDENT_3.search(message)
        if m:
            result["student_ref"] = m.group(1)
        return result
