"""后端置信度计算 — 始终用规则计算，不信赖 LLM 返回值。"""
import re


def compute_confidence(q: dict) -> float:
    """根据题型和答案内容计算置信度。"""
    qtype = q.get("type", "")
    answer = str(q.get("answer", "")).strip()

    if not answer:
        return 0.50

    if qtype in ("single_choice", "multi_choice"):
        if re.fullmatch(r'[A-Z]+', answer):
            return 0.95
        return 0.50

    if qtype == "fill_in_blank":
        if len(answer) <= 30:
            return 0.90
        return 0.70  # 答案过长，可能题型误判

    if qtype == "short_answer":
        return 0.85

    return 0.50
