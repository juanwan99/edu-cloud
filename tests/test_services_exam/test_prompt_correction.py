"""CORRECTION prompt tests (Task 14: OCR visual confusion recovery)."""
from edu_cloud.modules.grading.prompts import get_prompt, get_prompt_config, render_prompt


def test_correction_prompt_biology():
    prompt = get_prompt("biology", "CORRECTION", "senior")
    assert prompt is not None
    assert "{{geminiText}}" in prompt
    assert "{{baiduText}}" in prompt
    assert "OCR修正" in prompt


def test_correction_prompt_math():
    prompt = get_prompt("math", "CORRECTION", "senior")
    assert prompt is not None


def test_correction_prompt_chinese():
    prompt = get_prompt("chinese", "CORRECTION", "senior")
    assert prompt is not None


def test_correction_config():
    config = get_prompt_config("biology", "CORRECTION", "senior")
    assert config is not None
    assert config["temperature"] == 0


def test_correction_render():
    prompt = get_prompt("biology", "CORRECTION", "senior")
    rendered = render_prompt(prompt, {
        "geminiText": "动物细胞",
        "baiduText": "动物纲胞",
        "referenceInfo": "标准答案：动物细胞",
    })
    assert "动物细胞" in rendered
    assert "动物纲胞" in rendered
    assert "{{geminiText}}" not in rendered
