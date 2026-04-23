"""Phase 1-C: 题型分派 prompt 单测。"""
from edu_cloud.modules.grading.prompts_legacy import (
    build_grading_prompt,
    _SYSTEM_PROMPT_FILL_BLANK,
    _SYSTEM_PROMPT_ESSAY,
    _SYSTEM_PROMPT_GENERIC,
)


_RUBRIC = {"criteria": [{"point": "p1", "score": 5}]}
_QUESTION = {"name": "Q1", "max_score": 10}


def test_fill_blank_uses_short_answer_prompt():
    msgs = build_grading_prompt(_RUBRIC, _QUESTION, "fill_blank")
    assert msgs[0]["role"] == "system"
    assert msgs[0]["content"] == _SYSTEM_PROMPT_FILL_BLANK
    assert "填空题" in msgs[0]["content"]


def test_essay_uses_long_answer_prompt():
    msgs = build_grading_prompt(_RUBRIC, _QUESTION, "essay")
    assert msgs[0]["content"] == _SYSTEM_PROMPT_ESSAY
    assert "采分点" in msgs[0]["content"]


def test_unknown_type_falls_back_to_generic():
    for qt in (None, "", "choice", "weird"):
        msgs = build_grading_prompt(_RUBRIC, _QUESTION, qt)
        assert msgs[0]["content"] == _SYSTEM_PROMPT_GENERIC


def test_user_content_includes_rubric_and_max_score():
    msgs = build_grading_prompt(_RUBRIC, _QUESTION, "essay")
    user = msgs[1]
    assert user["role"] == "user"
    assert "Q1" in user["content"]
    assert "10" in user["content"]
    assert "p1" in user["content"]
