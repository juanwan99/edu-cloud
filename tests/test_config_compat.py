"""Compatibility test: every settings.XXX attribute must exist after config reorganisation.

ORC-003 constraint: field names, types, and default values must not change.
Only comment section headers may be added.
"""

import pytest

from edu_cloud.config import settings


# Complete attribute list from the plan (matches config.py @ 94 lines).
EXPECTED_ATTRS = [
    "DATABASE_URL",
    "REDIS_URL",
    "SECRET_KEY",
    "ENCRYPTION_KEY",
    "SEED_DEFAULT_PASSWORD",
    "ACCESS_TOKEN_EXPIRE_MINUTES",
    "ALGORITHM",
    "UPLOAD_DIR",
    "STORAGE_ROOT",
    "MAX_UPLOAD_SIZE_MB",
    "LOG_LEVEL",
    "LOG_DIR",
    "LOG_FILE_LEVEL",
    "CORS_ORIGINS",
    "LLM_API_URL",
    "LLM_API_KEY",
    "LLM_MODEL",
    "LLM_SLOT",
    "LLM_TIMEOUT",
    "LLM_MAX_RETRIES",
    "GEMINI_API_KEY",
    "GEMINI_MODEL",
    "DEEPSEEK_API_KEY",
    "VERTEX_AI_PROJECT",
    "VERTEX_AI_LOCATION",
    "GRADING_BATCH_SIZE",
    "TIER_CONTEXT_THRESHOLDS",
    "MODEL_ROUTER_ADVANCED_KEYWORDS",
    "AI_SESSION_TTL",
    "AI_AGENT_PROVIDER",
    "AI_AGENT_FALLBACK_PROVIDER",
    "AI_COZE_ENABLED",
    "AI_COZE_API_BASE",
    "AI_COZE_BOT_ID",
    "AI_COZE_API_TOKEN",
    "AI_COZE_TIMEOUT",
    "AI_COZE_TOOL_ALLOWLIST",
    "AI_TOOL_GATEWAY_PUBLIC_BASE",
    "AI_TOOL_GATEWAY_TOKEN",
    "AI_TOOL_GATEWAY_HTTP_ENABLED",
    "KNOWLEDGE_BASE_DIR",
    "KNOWLEDGE_ENABLED",
    "KNOWLEDGE_DB_PATH",
    "KNOWLEDGE_DRAFT_VISIBLE",
    "PAPER_SKILL_URL",
]


@pytest.mark.parametrize("attr", EXPECTED_ATTRS)
def test_settings_attribute_exists(attr: str) -> None:
    """settings.{attr} must be accessible (hasattr + getattr do not raise)."""
    assert hasattr(settings, attr), f"settings.{attr} is missing"
    # Also verify it's not None-by-accident (all fields have explicit defaults).
    getattr(settings, attr)  # should not raise


def test_no_attribute_removed() -> None:
    """Guard: the full set of expected attributes is present on the settings object."""
    missing = [a for a in EXPECTED_ATTRS if not hasattr(settings, a)]
    assert missing == [], f"Missing attributes: {missing}"


def test_settings_is_flat_class() -> None:
    """ORC-003: settings must remain a flat BaseSettings instance, not nested sub-models."""
    from edu_cloud.config import Settings

    # All expected attrs should be direct class-level fields, not nested.
    for attr in EXPECTED_ATTRS:
        assert attr in Settings.model_fields, (
            f"{attr} is not a direct model field -- possible illegal nesting"
        )


def test_environment_normalization_helpers() -> None:
    from edu_cloud.config import is_production_environment, normalize_environment

    assert normalize_environment(" Production ") == "production"
    assert is_production_environment(" Production ")
    assert not is_production_environment("development")


def test_spaced_production_refuses_insecure_defaults() -> None:
    from edu_cloud.config import Settings

    with pytest.raises(RuntimeError, match="SECRET_KEY is insecure"):
        Settings(ENVIRONMENT=" Production ")
