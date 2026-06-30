from edu_cloud.modules.grading.ocr_validator import (
    validate_ocr_blanks,
    is_blank_answer,
    recover_truncated_blanks,
    has_ocr_review_needed,
    ocr_review_needed_message,
)


def test_validate_cleans_whitespace():
    blanks = [{"blankNo": "1-1", "text": "  动物  细胞  "}]
    result = validate_ocr_blanks(blanks)
    assert result[0]["text"] == "动物 细胞"


def test_validate_filters_english_commentary():
    blanks = [{"blankNo": "1-1", "text": "The student wrote something illegible"}]
    result = validate_ocr_blanks(blanks)
    assert result[0]["text"] == "（无法辨识，需人工复核）"
    assert result[0]["needs_review"] is True
    assert result[0]["ocr_status"] == "needs_review"
    assert result[0]["review_reason"] == "ocr_english_commentary"


def test_validate_preserves_chinese_text():
    blanks = [{"blankNo": "1-1", "text": "光合作用的产物是氧气"}]
    result = validate_ocr_blanks(blanks)
    assert result[0]["text"] == "光合作用的产物是氧气"


def test_validate_preserves_mixed_text():
    blanks = [{"blankNo": "1-1", "text": "CO2 + H2O → 有机物"}]
    result = validate_ocr_blanks(blanks)
    assert result[0]["text"] == "CO2 + H2O → 有机物"


def test_validate_empty_list():
    assert validate_ocr_blanks([]) == []
    assert validate_ocr_blanks(None) == []


def test_is_blank_answer_true():
    assert is_blank_answer("") is True
    assert is_blank_answer("  ") is True
    assert is_blank_answer("（未作答）") is True
    assert is_blank_answer("[空]") is True
    assert is_blank_answer("[?]") is True


def test_is_blank_answer_false():
    assert is_blank_answer("动物细胞") is False
    assert is_blank_answer("A") is False
    assert is_blank_answer("（无法辨识）") is False
    assert is_blank_answer("（无法辨识，需人工复核）") is False


def test_recover_truncated_pads():
    blanks = [
        {"blankNo": "1-1", "text": "A"},
        {"blankNo": "1-2", "text": "B"},
    ]
    result = recover_truncated_blanks(blanks, 4)
    assert len(result) == 4
    assert result[2]["text"] == "（无法辨识，需人工复核）"
    assert result[2]["needs_review"] is True
    assert result[2]["review_reason"] == "ocr_missing_blank"
    assert result[3]["text"] == "（无法辨识，需人工复核）"
    assert result[3]["needs_review"] is True
    assert result[3]["review_reason"] == "ocr_missing_blank"


def test_recover_truncated_no_padding_needed():
    blanks = [{"blankNo": "1-1", "text": "A"}, {"blankNo": "1-2", "text": "B"}]
    result = recover_truncated_blanks(blanks, 2)
    assert len(result) == 2


def test_recover_truncated_empty():
    result = recover_truncated_blanks([], 3)
    assert len(result) == 3
    assert all(b["text"] == "（无法辨识，需人工复核）" for b in result)
    assert all(b["needs_review"] is True for b in result)


def test_ocr_review_needed_helpers_detect_marked_blanks():
    blanks = [
        {"blankNo": "1-1", "text": "A"},
        {
            "blankNo": "1-2",
            "text": "（无法辨识，需人工复核）",
            "needs_review": True,
            "ocr_status": "needs_review",
            "review_reason": "ocr_missing_blank",
        },
    ]

    assert has_ocr_review_needed(blanks) is True
    assert "ocr_missing_blank" in ocr_review_needed_message(blanks)


def test_ocr_review_needed_helpers_ignore_normal_blanks():
    blanks = [{"blankNo": "1-1", "text": "动物细胞"}]

    assert has_ocr_review_needed(blanks) is False
