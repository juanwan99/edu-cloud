"""生产环境启动检查 — fail-closed 策略"""
import logging
import os

logger = logging.getLogger("edu_cloud.startup")

_INSECURE_DEFAULTS = {
    "SECRET_KEY": "change-me",
    "ENCRYPTION_KEY": "change-me-in-production",
    "SEED_DEFAULT_PASSWORD": "change-me-seed-password",
}


def check_critical_secrets(settings) -> list[str]:
    """检查关键密钥是否使用了默认值。返回错误列表。"""
    errors = []
    for attr, default_val in _INSECURE_DEFAULTS.items():
        if getattr(settings, attr, None) == default_val:
            errors.append(f"{attr} 使用了不安全的默认值，必须在 .env 中覆盖")
    return errors


async def check_database(settings) -> list[str]:
    """验证数据库可连接。"""
    errors = []
    if settings.DATABASE_URL.startswith("sqlite"):
        return errors  # SQLite 内存库不需要检查
    try:
        from sqlalchemy.ext.asyncio import create_async_engine
        from sqlalchemy import text
        engine = create_async_engine(settings.DATABASE_URL, echo=False)
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        await engine.dispose()
    except Exception as e:
        errors.append(f"数据库连接失败: {e}")
    return errors


async def check_redis(settings) -> list[str]:
    """验证 Redis 可连接。"""
    errors = []
    try:
        from redis.asyncio import from_url
        r = await from_url(settings.REDIS_URL)
        await r.ping()
        await r.aclose()
    except Exception as e:
        errors.append(f"Redis 连接失败: {e}")
    return errors


async def run_startup_checks(settings) -> None:
    """执行所有启动检查。失败则抛出 RuntimeError 阻断启动。"""
    if os.getenv("SKIP_STARTUP_CHECKS", "").strip() in ("1", "true", "yes"):
        logger.info("SKIP_STARTUP_CHECKS=1, 跳过启动检查")
        return

    errors = []
    errors.extend(check_critical_secrets(settings))
    errors.extend(await check_database(settings))
    errors.extend(await check_redis(settings))

    if errors:
        for e in errors:
            logger.critical("启动检查失败: %s", e)
        raise RuntimeError(
            f"启动检查失败 ({len(errors)} 项):\n" + "\n".join(f"  - {e}" for e in errors)
        )
    logger.info("所有启动检查通过")
