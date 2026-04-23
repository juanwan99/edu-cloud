"""Prompt dispatcher tests (Task 2: subject-specific template rendering)."""
import pytest
from edu_cloud.modules.grading.prompts import get_prompt, render_prompt, get_prompt_config


def test_render_prompt_replaces_variables():
    template = "满分{{fullScore}}分\n细则：{{rubric}}"
    result = render_prompt(template, {"fullScore": "12", "rubric": "test"})
    assert result == "满分12分\n细则：test"


def test_render_prompt_preserves_unknown():
    result = render_prompt("{{known}} and {{unknown}}", {"known": "yes"})
    assert result == "yes and {{unknown}}"


def test_get_prompt_biology_grading():
    prompt = get_prompt("biology", "GRADING", "senior")
    assert prompt is not None
    assert "{{fullScore}}" in prompt
    assert "{{rubric}}" in prompt


def test_get_prompt_biology_rubric_generation():
    prompt = get_prompt("biology", "RUBRIC_GENERATION", "senior")
    assert prompt is not None
    assert "{{fullScore}}" in prompt


def test_get_prompt_unknown_subject():
    prompt = get_prompt("underwater_basket_weaving", "GRADING", "senior")
    assert prompt is None


def test_get_prompt_config():
    config = get_prompt_config("biology", "GRADING", "senior")
    assert config is not None
    assert "temperature" in config


def test_get_prompt_math_grading():
    prompt = get_prompt("math", "GRADING", "senior")
    assert prompt is not None
    assert "等价" in prompt


def test_get_prompt_chinese_grading():
    prompt = get_prompt("chinese", "GRADING", "senior")
    assert prompt is not None
    assert "默写" in prompt
