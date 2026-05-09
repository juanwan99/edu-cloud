from edu_cloud.modules.grading.rubric_formatter import format_rubric_for_grading


def test_basic_format():
    items = [
        {"blankNo": "1-1", "score": 2, "standardAnswer": "动物细胞",
         "context": "图中有中心体无细胞壁", "judgingRules": "满分：答出动物细胞"},
    ]
    result = format_rubric_for_grading(items)
    assert "【第1-1空】（2分）" in result
    assert "标准答案：动物细胞" in result
    assert "背景与逻辑：图中有中心体无细胞壁" in result
    assert "判分细则：满分：答出动物细胞" in result


def test_fallback_answer_field():
    items = [{"blankNo": "1", "score": 3, "answer": "fallback answer"}]
    result = format_rubric_for_grading(items)
    assert "标准答案：fallback answer" in result


def test_multiple_items_separated():
    items = [
        {"blankNo": "1-1", "score": 2, "standardAnswer": "A"},
        {"blankNo": "1-2", "score": 3, "standardAnswer": "B"},
    ]
    result = format_rubric_for_grading(items)
    assert "---" in result
    assert "【第1-1空】" in result
    assert "【第1-2空】" in result


def test_empty_list():
    assert format_rubric_for_grading([]) == ""
    assert format_rubric_for_grading(None) == ""
