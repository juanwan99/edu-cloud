"""Junior-level prompt inheritance tests (Task 13)."""
from edu_cloud.modules.grading.prompts import get_prompt, get_prompt_config


def test_junior_biology_grading():
    prompt = get_prompt("biology", "GRADING", "junior")
    assert prompt is not None
    assert "{{fullScore}}" in prompt
    assert "{{rubric}}" in prompt


def test_junior_biology_metadata():
    """Junior module overrides NAME/LEVEL/ROLE but inherits prompts."""
    from edu_cloud.modules.grading.prompts import _load_subject
    data = _load_subject("biology", "junior")
    assert data is not None
    assert data["LEVEL"] == "junior"
    assert data["ROLE"] == "初中生物阅卷专家"


def test_junior_math_grading():
    prompt = get_prompt("math", "GRADING", "junior")
    assert prompt is not None


def test_junior_chinese_grading():
    prompt = get_prompt("chinese", "GRADING", "junior")
    assert prompt is not None


def test_junior_all_subjects_load():
    """All 9 junior subjects should load."""
    subjects = ["biology", "math", "chinese", "physics", "chemistry",
                "english", "politics", "history", "geography"]
    for subj in subjects:
        prompt = get_prompt(subj, "GRADING", "junior")
        assert prompt is not None, f"Junior {subj} GRADING prompt not found"


def test_junior_config_inherited():
    config = get_prompt_config("biology", "GRADING", "junior")
    assert config is not None
    assert config["temperature"] == 0


def test_junior_fallback_to_senior():
    """Unknown junior subject falls back to senior if available."""
    from edu_cloud.modules.grading.prompts import _load_subject, _cache
    # Clear cache to test fallback
    _cache.pop("junior/biology", None)
    data = _load_subject("biology", "junior")
    assert data is not None


def test_senior_unaffected():
    """Senior prompts still work after junior addition."""
    prompt = get_prompt("biology", "GRADING", "senior")
    assert prompt is not None
