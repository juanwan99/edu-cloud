"""答案文档解析器 — 从 .docx 提取结构化题目答案数据。

支持格式：
  17（共11分，除标注外每空2分）
  （1）答案文本
  （2）答案1     答案2（3分）
"""
from __future__ import annotations

import re
import logging
from pathlib import Path

logger = logging.getLogger(__name__)


def parse_answer_docx(path: str | Path) -> list[dict]:
    """解析答案 docx 文件，返回结构化题目列表。

    Returns:
        [{
            "qno": 17,
            "total_score": 11,
            "default_score_per_blank": 2,
            "subs": [
                {"sub": 1, "answers": ["不产生NADPH"]},
                {"sub": 2, "answers": ["专一性"]},
                ...
            ]
        }, ...]
    """
    from docx import Document

    doc = Document(str(path))
    lines = [p.text.strip() for p in doc.paragraphs if p.text.strip()]

    questions = []
    current_q = None

    for line in lines:
        # 匹配大题标题：17（共11分，除标注外每空2分）
        m = re.match(r'^(\d+)[．.、\s]*[（(]共?\s*(\d+)\s*分', line)
        if m:
            if current_q:
                questions.append(current_q)
            qno = int(m.group(1))
            total_score = int(m.group(2))
            # 提取默认每空分值
            dm = re.search(r'每空\s*(\d+)\s*分', line)
            default_per_blank = int(dm.group(1)) if dm else 2
            current_q = {
                "qno": qno,
                "total_score": total_score,
                "default_score_per_blank": default_per_blank,
                "subs": [],
            }
            continue

        if not current_q:
            continue

        # 匹配小问：（1）答案  或 ①答案
        sm = re.match(r'^[（(](\d+)[）)](.*)$', line)
        if sm:
            sub_no = int(sm.group(1))
            rest = sm.group(2).strip()
            answers = _split_answers(rest)
            current_q["subs"].append({"sub": sub_no, "answers": answers})
            continue

        # 匹配带圈数字小问（行首独立成行）：①答案 → 创建新 sub
        cm = re.match(r'^([①②③④⑤⑥⑦⑧⑨⑩])(.*)', line)
        if cm:
            circle_char = cm.group(1)
            rest = cm.group(2).strip()
            answers = _split_answers(rest)
            next_sub = (current_q["subs"][-1]["sub"] + 1) if current_q["subs"] else 1
            current_q["subs"].append({
                "sub": next_sub,
                "label": circle_char,
                "answers": answers,
            })
            continue

        # 其他行：追加到当前最后一个小问
        if current_q["subs"]:
            answers = _split_answers(line)
            current_q["subs"][-1]["answers"].extend(answers)

    if current_q:
        questions.append(current_q)

    logger.info("parse_answer_docx: %s → %d questions", path, len(questions))
    return questions


def _split_answers(text: str) -> list[str]:
    """拆分同一行内的多个答案（用多空格或制表符分隔）。

    去除尾部的分值标注如 (3分) （2分，一点1分）。
    """
    if not text:
        return []
    # 按多空格或 tab 分隔
    parts = re.split(r'\s{3,}|\t+', text)
    results = []
    for p in parts:
        p = p.strip()
        if not p:
            continue
        # 去除尾部分值标注
        p = re.sub(r'[（(]\d+分[^）)]*[）)]$', '', p).strip()
        p = re.sub(r'[（(]共\d+分[^）)]*[）)]$', '', p).strip()
        # 去除尾部纯标点（答案原文的人工分隔符，如尾部的；。）
        p = re.sub(r'[；;。.，,]+$', '', p).strip()
        if p:
            results.append(p)
    return results if results else []
