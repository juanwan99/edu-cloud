from edu_cloud.modules.card.confidence import compute_confidence


def test_choice_valid():
    assert compute_confidence({"type": "single_choice", "answer": "A", "sub_count": 1}) == 0.95


def test_choice_invalid_answer():
    assert compute_confidence({"type": "single_choice", "answer": "", "sub_count": 1}) == 0.50


def test_multi_choice_valid():
    assert compute_confidence({"type": "multi_choice", "answer": "ABD", "sub_count": 1}) == 0.95


def test_fill_valid():
    assert compute_confidence({"type": "fill_in_blank", "answer": "x=3", "sub_count": 1}) == 0.90


def test_fill_long_answer():
    """填空答案超过 30 字符 → 降为 0.70（可能是题型误判）。"""
    assert compute_confidence({"type": "fill_in_blank", "answer": "a" * 31, "sub_count": 1}) == 0.70


def test_short_answer_with_subs():
    assert compute_confidence({"type": "short_answer", "answer": "(1)...(2)...", "sub_count": 2}) == 0.85


def test_empty_answer():
    assert compute_confidence({"type": "short_answer", "answer": "", "sub_count": 1}) == 0.50
