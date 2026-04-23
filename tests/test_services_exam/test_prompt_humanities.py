"""Humanities subject prompt tests (Task 10: english, politics, history, geography)."""
from edu_cloud.modules.grading.prompts import get_prompt


def test_get_prompt_english_grading():
    prompt = get_prompt("english", "GRADING", "senior")
    assert prompt is not None
    assert "拼写" in prompt


def test_get_prompt_english_grading_text():
    prompt = get_prompt("english", "GRADING_TEXT", "senior")
    assert prompt is not None
    assert "{{extractedText}}" in prompt
    assert "拼写" in prompt


def test_get_prompt_english_rubric_generation():
    prompt = get_prompt("english", "RUBRIC_GENERATION", "senior")
    assert prompt is not None
    assert "{{fullScore}}" in prompt


def test_get_prompt_politics_grading():
    prompt = get_prompt("politics", "GRADING", "senior")
    assert prompt is not None
    assert "原理" in prompt


def test_get_prompt_politics_grading_text():
    prompt = get_prompt("politics", "GRADING_TEXT", "senior")
    assert prompt is not None
    assert "{{extractedText}}" in prompt
    assert "原理" in prompt


def test_get_prompt_politics_rubric_generation():
    prompt = get_prompt("politics", "RUBRIC_GENERATION", "senior")
    assert prompt is not None
    assert "{{fullScore}}" in prompt


def test_get_prompt_history_grading():
    prompt = get_prompt("history", "GRADING", "senior")
    assert prompt is not None
    assert "史实" in prompt or "时间" in prompt


def test_get_prompt_history_grading_text():
    prompt = get_prompt("history", "GRADING_TEXT", "senior")
    assert prompt is not None
    assert "{{extractedText}}" in prompt


def test_get_prompt_history_rubric_generation():
    prompt = get_prompt("history", "RUBRIC_GENERATION", "senior")
    assert prompt is not None
    assert "{{fullScore}}" in prompt


def test_get_prompt_geography_grading():
    prompt = get_prompt("geography", "GRADING", "senior")
    assert prompt is not None
    assert "方位" in prompt


def test_get_prompt_geography_grading_text():
    prompt = get_prompt("geography", "GRADING_TEXT", "senior")
    assert prompt is not None
    assert "{{extractedText}}" in prompt
    assert "方位" in prompt


def test_get_prompt_geography_rubric_generation():
    prompt = get_prompt("geography", "RUBRIC_GENERATION", "senior")
    assert prompt is not None
    assert "{{fullScore}}" in prompt
