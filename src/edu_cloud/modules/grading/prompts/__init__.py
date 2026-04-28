"""Subject-specific prompt dispatch system.

Usage:
    from edu_cloud.modules.grading.prompts import get_prompt, render_prompt
    template = get_prompt("biology", "GRADING", "senior")
    prompt = render_prompt(template, {"fullScore": "12", "rubric": rubric_text})
"""
import re
import importlib
import logging

logger = logging.getLogger(__name__)

_SUBJECTS = {
    "biology", "math", "chinese", "physics", "chemistry",
    "english", "politics", "history", "geography",
}

_CODE_TO_SUBJECT = {
    "YW": "chinese", "yw": "chinese",
    "SX": "math", "sx": "math",
    "YY": "english", "yy": "english",
    "SW": "biology", "sw": "biology",
    "WL": "physics", "wl": "physics",
    "HX": "chemistry", "hx": "chemistry",
    "ZZ": "politics", "zz": "politics",
    "LS": "history", "ls": "history",
    "DL": "geography", "dl": "geography",
}

_cache: dict[str, dict] = {}


def _load_subject(subject: str, level: str = "senior") -> dict | None:
    subject = _CODE_TO_SUBJECT.get(subject, subject)
    key = f"{level}/{subject}"
    if key in _cache:
        return _cache[key]

    # Try level-specific module first (e.g., junior.biology), then fallback to senior
    mod = None
    if level != "senior":
        try:
            mod = importlib.import_module(f".{level}.{subject}", package=__name__)
        except ModuleNotFoundError:
            pass

    if mod is None:
        try:
            mod = importlib.import_module(f".{subject}", package=__name__)
        except ModuleNotFoundError:
            logger.warning("prompt module not found: %s", key)
            _cache[key] = None
            return None

    data = {
        "name": getattr(mod, "NAME", subject),
        "level": getattr(mod, "LEVEL", level),
        "role": getattr(mod, "ROLE", f"{subject}阅卷专家"),
    }
    for attr in dir(mod):
        if attr.isupper() and not attr.startswith("_"):
            data[attr] = getattr(mod, attr)

    _cache[key] = data
    return data


def get_prompt(subject: str, prompt_type: str, level: str = "senior") -> str | None:
    mod = _load_subject(subject, level)
    if mod is None:
        return None
    return mod.get(prompt_type)


def get_prompt_config(subject: str, prompt_type: str, level: str = "senior") -> dict | None:
    mod = _load_subject(subject, level)
    if mod is None:
        return None
    return mod.get(f"{prompt_type}_CONFIG")


def render_prompt(template: str, variables: dict) -> str:
    if not template:
        return ""
    return re.sub(
        r"\{\{(\w+)\}\}",
        lambda m: str(variables.get(m.group(1), m.group(0))),
        template,
    )
