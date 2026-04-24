import pytest
from unittest.mock import patch, AsyncMock

from edu_cloud.modules.card.parser.answer_standardizer import (
    _fallback_heuristic, parse_pdf_answers, _get_llm_endpoint,
)


def test_fallback_single_choice():
    parsed = [{"number": 1, "answer_text": "A", "image_count": 0}]
    result = _fallback_heuristic(parsed)
    assert result[0]["type"] == "single_choice"
    assert result[0]["options_count"] == 4


def test_fallback_multi_choice():
    parsed = [{"number": 2, "answer_text": "BD", "image_count": 0}]
    result = _fallback_heuristic(parsed)
    assert result[0]["type"] == "multi_choice"


def test_fallback_fill_blank():
    parsed = [{"number": 13, "answer_text": "x=3", "image_count": 0}]
    result = _fallback_heuristic(parsed)
    assert result[0]["type"] == "fill_in_blank"


def test_fallback_short_answer():
    parsed = [{"number": 15, "answer_text": "（1）证明：" + "解题过程" * 20, "image_count": 0}]
    result = _fallback_heuristic(parsed)
    assert result[0]["type"] == "short_answer"
    assert result[0]["sub_count"] >= 1


def test_fallback_empty_input():
    result = _fallback_heuristic([])
    assert result == []


def test_fallback_mixed_types():
    parsed = [
        {"number": 1, "answer_text": "A", "image_count": 0},
        {"number": 2, "answer_text": "BC", "image_count": 0},
        {"number": 3, "answer_text": "42", "image_count": 0},
        {"number": 4, "answer_text": "这是一道需要详细解答的题目" * 5, "image_count": 0},
    ]
    result = _fallback_heuristic(parsed)
    assert len(result) == 4
    assert result[0]["type"] == "single_choice"
    assert result[1]["type"] == "multi_choice"
    assert result[2]["type"] == "fill_in_blank"
    assert result[3]["type"] == "short_answer"


def test_fallback_no_score_field():
    """fallback 返回 score=None（不推断分值）。"""
    parsed = [
        {"number": 1, "answer_text": "A", "image_count": 0},
        {"number": 2, "answer_text": "详细解答" * 20, "image_count": 0},
    ]
    result = _fallback_heuristic(parsed)
    for q in result:
        assert q["score"] is None


def test_has_sufficient_text_true():
    """每页平均 >50 字符时判定为有文字层。"""
    from edu_cloud.modules.card.parser.answer_standardizer import _has_sufficient_text
    text_by_page = ["一、选择题答案：1.A 2.B 3.C 4.D 5.A 6.B 7.C 8.D" * 3, "二、填空题" * 10]
    assert _has_sufficient_text(text_by_page) is True


def test_has_sufficient_text_false():
    """每页平均 ≤50 字符（扫描件）→ False。"""
    from edu_cloud.modules.card.parser.answer_standardizer import _has_sufficient_text
    text_by_page = ["", "", "  ", ""]
    assert _has_sufficient_text(text_by_page) is False


def test_has_sufficient_text_empty():
    from edu_cloud.modules.card.parser.answer_standardizer import _has_sufficient_text
    assert _has_sufficient_text([]) is False


def test_text_to_paragraphs():
    """将按页文字转换为 (text, image_count) 元组列表。"""
    from edu_cloud.modules.card.parser.answer_standardizer import _text_to_paragraphs
    text_by_page = ["1.A\n2.B\n\n3.C", "4.D"]
    result = _text_to_paragraphs(text_by_page)
    assert all(isinstance(p, tuple) and len(p) == 2 for p in result)
    texts = [p[0] for p in result]
    assert "" not in texts
    assert all(p[1] == 0 for p in result)


def test_settings_has_llm_config():
    from edu_cloud.config import Settings
    s = Settings(LLM_API_URL="http://x", LLM_API_KEY="k", LLM_MODEL="flash")
    assert hasattr(s, 'LLM_MODEL')
    assert isinstance(s.LLM_MODEL, str)


def test_fallback_single_digit():
    """单字符数字 '3' → fill_in_blank, confidence 0.90。"""
    parsed = [{"number": 1, "answer_text": "3", "image_count": 0}]
    result = _fallback_heuristic(parsed)
    assert result[0]["type"] == "fill_in_blank"
    assert result[0]["confidence"] == 0.90


def test_fallback_boundary_29_chars():
    """29 字符 → fill_in_blank。"""
    parsed = [{"number": 1, "answer_text": "a" * 29, "image_count": 0}]
    result = _fallback_heuristic(parsed)
    assert result[0]["type"] == "fill_in_blank"
    assert result[0]["confidence"] == 0.90


def test_fallback_boundary_30_chars():
    """恰好 30 字符 → fill_in_blank（<= 30 边界）。"""
    parsed = [{"number": 1, "answer_text": "a" * 30, "image_count": 0}]
    result = _fallback_heuristic(parsed)
    assert result[0]["type"] == "fill_in_blank"
    assert result[0]["confidence"] == 0.90


def test_fallback_boundary_31_chars():
    """31 字符 → short_answer。"""
    parsed = [{"number": 1, "answer_text": "a" * 31, "image_count": 0}]
    result = _fallback_heuristic(parsed)
    assert result[0]["type"] == "short_answer"
    assert result[0]["confidence"] == 0.85


def test_fallback_returns_new_fields():
    """fallback 必须返回 section, confidence, warnings 字段，score=None。"""
    parsed = [
        {"number": 1, "answer_text": "A", "image_count": 0},
        {"number": 2, "answer_text": "详细解答" * 20, "image_count": 0},
    ]
    result = _fallback_heuristic(parsed)
    for q in result:
        assert "section" in q and q["section"] is None
        assert "score" in q and q["score"] is None
        assert "confidence" in q and 0 < q["confidence"] <= 1
        assert "warnings" in q and isinstance(q["warnings"], list)
    # 选择题置信度 0.95
    assert result[0]["confidence"] == 0.95
    # 解答题置信度 0.85
    assert result[1]["confidence"] == 0.85


# --- parse_pdf_answers 三路分流测试（mock 级） ---

@pytest.mark.asyncio
async def test_parse_pdf_text_path():
    """有文字层 + 正则匹配成功 → text_llm 路径。"""
    fake_pages = ["1.A 2.B 3.C 4.D 5.A 6.B 7.C 8.D 答案" * 5] * 3  # 每页 >50 字符平均
    fake_parsed = [{"number": 1, "answer_text": "A", "image_count": 0}]
    fake_standardized = [{"number": 1, "type": "single_choice", "answer": "A",
                          "options_count": 4, "sub_count": 1}]

    with patch("edu_cloud.modules.card.parser.answer_standardizer._extract_pdf_text", return_value=fake_pages), \
         patch("edu_cloud.modules.card.parser.word_parser._match_paragraphs", return_value=fake_parsed), \
         patch("edu_cloud.modules.card.parser.answer_standardizer.standardize_answers",
               new_callable=AsyncMock, return_value=fake_standardized):
        result, method = await parse_pdf_answers("/fake.pdf")
        assert method == "text_llm"
        assert len(result) == 1


@pytest.mark.asyncio
async def test_parse_pdf_text_path_fallback_to_vision():
    """有文字层但正则匹配失败 → 降级 vision_llm。"""
    fake_pages = ["页眉页脚" * 20] * 3  # 有文字但正则不匹配
    fake_standardized = [{"number": 1, "type": "single_choice", "answer": "A",
                          "options_count": 4, "sub_count": 1}]

    with patch("edu_cloud.modules.card.parser.answer_standardizer._extract_pdf_text", return_value=fake_pages), \
         patch("edu_cloud.modules.card.parser.word_parser._match_paragraphs", return_value=[]), \
         patch("edu_cloud.modules.card.parser.answer_standardizer.standardize_from_pdf",
               new_callable=AsyncMock, return_value=fake_standardized):
        result, method = await parse_pdf_answers("/fake.pdf")
        assert method == "vision_llm"
        assert len(result) == 1


@pytest.mark.asyncio
async def test_parse_pdf_vision_path():
    """无文字层（扫描件）→ vision_llm 路径。"""
    fake_pages = ["", "", ""]  # 空页
    fake_standardized = [{"number": 1, "type": "single_choice", "answer": "A",
                          "options_count": 4, "sub_count": 1}]

    with patch("edu_cloud.modules.card.parser.answer_standardizer._extract_pdf_text", return_value=fake_pages), \
         patch("edu_cloud.modules.card.parser.answer_standardizer.standardize_from_pdf",
               new_callable=AsyncMock, return_value=fake_standardized):
        result, method = await parse_pdf_answers("/fake.pdf")
        assert method == "vision_llm"
        assert len(result) == 1


# _get_llm_endpoint proxy contract tests removed:
# edu-cloud doesn't have LLM_PROXY_URL config field.
# LLM routing in edu-cloud goes through LLM_API_URL (pointing to llm-proxy).
