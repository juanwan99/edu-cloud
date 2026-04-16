"""选择题判分共享函数 — pipeline 和 router 共用。"""


def grade_objective_answer(
    detected_answer: str | None,
    correct_answer: str | None,
    max_score: float,
) -> tuple[float, bool]:
    """比对检测答案与标准答案，返回 (score, is_correct)。

    - 大小写不敏感
    - 多选题顺序不敏感（按字符排序比对）
    - detected 或 correct 为 None 视为空字符串
    """
    detected = (detected_answer or "").upper()
    correct = (correct_answer or "").upper()
    is_correct = sorted(detected) == sorted(correct)
    score = max_score if is_correct else 0.0
    return score, is_correct
