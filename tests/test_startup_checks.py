"""startup_checks 单元测试"""
import pytest
from unittest.mock import AsyncMock, patch
from edu_cloud.startup_checks import check_critical_secrets, run_startup_checks


class FakeSettings:
    SECRET_KEY = "change-me"
    ENCRYPTION_KEY = "change-me-in-production"
    SEED_DEFAULT_PASSWORD = "change-me-seed-password"
    DATABASE_URL = "sqlite+aiosqlite:///:memory:"
    REDIS_URL = "redis://localhost:6379/0"


class SafeSettings(FakeSettings):
    SECRET_KEY = "a-real-production-key-32chars!!"
    ENCRYPTION_KEY = "a-real-encryption-key-here!!!!"
    SEED_DEFAULT_PASSWORD = "strong-seed-pw-2026!"


class ProductionSafeSettings(SafeSettings):
    ENVIRONMENT = "production"


def test_insecure_defaults_detected():
    errors = check_critical_secrets(FakeSettings())
    assert len(errors) == 3
    assert any("SECRET_KEY" in e for e in errors)


def test_safe_settings_pass():
    errors = check_critical_secrets(SafeSettings())
    assert len(errors) == 0


def test_insecure_defaults_include_env_in_non_dev():
    """非 development 环境的错误消息中应包含 ENVIRONMENT 信息"""
    class StagingSettings(FakeSettings):
        ENVIRONMENT = "staging"

    errors = check_critical_secrets(StagingSettings())
    assert len(errors) == 3
    assert all("ENVIRONMENT=staging" in e for e in errors)


def test_insecure_defaults_omit_env_in_dev():
    """development 环境的错误消息不包含 ENVIRONMENT 标签"""
    class DevSettings(FakeSettings):
        ENVIRONMENT = "development"

    errors = check_critical_secrets(DevSettings())
    assert len(errors) == 3
    assert all("ENVIRONMENT=" not in e for e in errors)


def test_insecure_defaults_normalize_dev_env():
    class DevSettings(FakeSettings):
        ENVIRONMENT = " Development "

    errors = check_critical_secrets(DevSettings())
    assert len(errors) == 3
    assert all("ENVIRONMENT=" not in e for e in errors)


def test_insecure_defaults_no_env_attr_defaults_to_dev():
    """没有 ENVIRONMENT 属性时按 development 处理"""
    errors = check_critical_secrets(FakeSettings())
    assert len(errors) == 3
    assert all("ENVIRONMENT=" not in e for e in errors)


@pytest.mark.asyncio
async def test_run_startup_checks_fails_on_defaults(monkeypatch):
    monkeypatch.delenv("SKIP_STARTUP_CHECKS", raising=False)
    with pytest.raises(RuntimeError, match="启动检查失败"):
        await run_startup_checks(FakeSettings())


@pytest.mark.parametrize("skip_value", ["1", "true", "yes"])
@pytest.mark.asyncio
async def test_run_startup_checks_skip_env_non_production(monkeypatch, skip_value):
    monkeypatch.setenv("SKIP_STARTUP_CHECKS", skip_value)

    with patch("edu_cloud.startup_checks.check_critical_secrets") as mock_secrets:
        with patch("edu_cloud.startup_checks.check_database", new_callable=AsyncMock) as mock_database:
            with patch("edu_cloud.startup_checks.check_redis", new_callable=AsyncMock) as mock_redis:
                await run_startup_checks(FakeSettings())  # 不应抛出

    mock_secrets.assert_not_called()
    mock_database.assert_not_awaited()
    mock_redis.assert_not_awaited()


@pytest.mark.asyncio
async def test_run_startup_checks_ignores_skip_env_in_production(monkeypatch):
    monkeypatch.setenv("SKIP_STARTUP_CHECKS", "yes")

    with patch("edu_cloud.startup_checks.check_database", new_callable=AsyncMock) as mock_database:
        with patch("edu_cloud.startup_checks.check_redis", new_callable=AsyncMock) as mock_redis:
            mock_database.return_value = []
            mock_redis.return_value = []
            with patch("edu_cloud.startup_checks.logger.warning") as mock_warning:
                await run_startup_checks(ProductionSafeSettings())

    mock_database.assert_awaited_once()
    mock_redis.assert_awaited_once()
    mock_warning.assert_called_once_with(
        "SKIP_STARTUP_CHECKS=%s ignored in production; startup checks will run",
        "yes",
    )
