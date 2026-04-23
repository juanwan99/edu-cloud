"""Tests for LLM config routing in grading worker — DB-resolved vs .env fallback."""
import pytest
from unittest.mock import AsyncMock, patch, MagicMock

from edu_cloud.workers.grading import _create_llm_client


def test_create_llm_client_with_defaults():
    """Uses .env settings when no overrides provided."""
    client = _create_llm_client()
    assert client.api_url is not None
    assert client.model is not None


def test_create_llm_client_with_overrides():
    """DB-resolved values override .env."""
    client = _create_llm_client(
        api_url="http://custom:8100",
        api_key="custom-key",
        model="custom-model",
    )
    assert client.api_url == "http://custom:8100"
    assert client.api_key == "custom-key"
    assert client.model == "custom-model"


def test_create_llm_client_partial_override():
    """Partial overrides: only provided values replace .env."""
    from edu_cloud.config import settings

    client = _create_llm_client(api_url="http://override:9000")
    assert client.api_url == "http://override:9000"
    # Non-overridden fields fall back to settings
    assert client.api_key == settings.LLM_API_KEY
    assert client.model == settings.LLM_MODEL


def test_create_llm_client_none_values_use_defaults():
    """Explicit None values fall back to .env (same as no args)."""
    from edu_cloud.config import settings

    client = _create_llm_client(api_url=None, api_key=None, model=None)
    assert client.api_url == settings.LLM_API_URL.rstrip("/")
    assert client.api_key == settings.LLM_API_KEY
    assert client.model == settings.LLM_MODEL


def test_create_llm_client_signature():
    """_create_llm_client accepts optional api_url, api_key, model params."""
    import inspect
    sig = inspect.signature(_create_llm_client)
    params = sig.parameters
    assert "api_url" in params
    assert "api_key" in params
    assert "model" in params
    # All should have None defaults
    for name in ("api_url", "api_key", "model"):
        assert params[name].default is None
