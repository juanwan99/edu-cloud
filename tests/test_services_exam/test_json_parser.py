import pytest
from edu_cloud.modules.grading.json_parser import extract_json


def test_clean_json():
    assert extract_json('{"score": 5}') == {"score": 5}


def test_markdown_code_block():
    text = '```json\n{"score": 5}\n```'
    assert extract_json(text) == {"score": 5}


def test_markdown_no_lang():
    text = '```\n{"score": 5}\n```'
    assert extract_json(text) == {"score": 5}


def test_text_before_json():
    text = 'Here is my analysis:\n{"score": 5, "comment": "good"}'
    assert extract_json(text) == {"score": 5, "comment": "good"}


def test_json_array():
    text = '[{"blankNo": "1", "score": 3}]'
    result = extract_json(text)
    assert isinstance(result, list)
    assert result[0]["blankNo"] == "1"


def test_nested_braces():
    text = '{"score": 5, "details": [{"sub": {"a": 1}}]}'
    assert extract_json(text)["details"][0]["sub"]["a"] == 1


def test_garbage_returns_none():
    assert extract_json("I cannot grade this image") is None


def test_truncated_json():
    text = '{"score": 5, "details": [{"blank": "1"'
    result = extract_json(text)
    assert result is not None
    assert result["score"] == 5
