"""Token revocation store backed by Redis.

Revoked JTIs are stored in a Redis SET with TTL matching token expiry.
Production revocation checks fail closed if Redis is unavailable.
"""
import logging
from edu_cloud.config import normalize_environment, settings

logger = logging.getLogger(__name__)

_REVOKE_PREFIX = "revoked_jti:"
_FAIL_OPEN_ENVIRONMENTS = {"development", "dev", "local", "test", "testing"}


def _environment_is_explicitly_configured() -> bool:
    return "ENVIRONMENT" in getattr(settings, "model_fields_set", set())


def revocation_checks_fail_closed() -> bool:
    """Do not accept tokens when revocation state is unknown.

    Fail-open is reserved for explicitly configured local/dev/test environments.
    A missing ENVIRONMENT must not silently inherit the default development
    value and weaken production deployments.
    """
    env = normalize_environment(settings.ENVIRONMENT)
    return not (_environment_is_explicitly_configured() and env in _FAIL_OPEN_ENVIRONMENTS)


async def _get_redis():
    try:
        import redis.asyncio as aioredis
        r = aioredis.from_url(settings.REDIS_URL, decode_responses=True)
        await r.ping()
        return r
    except Exception:
        return None


async def revoke_token(jti: str, ttl_seconds: int | None = None) -> bool:
    """Add a JTI to the revocation set. Returns True if stored."""
    r = await _get_redis()
    if r is None:
        logger.warning("token_revoke: Redis unavailable, skipping")
        return False
    try:
        key = f"{_REVOKE_PREFIX}{jti}"
        ttl = ttl_seconds or (settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60)
        await r.setex(key, ttl, "1")
        return True
    except Exception as e:
        logger.warning("token_revoke: failed: %s", e)
        return False
    finally:
        await r.aclose()


async def is_revoked(jti: str) -> bool:
    """Check if a JTI has been revoked.

    Development/test keeps the previous explicit fail-open behavior so local
    work is not hard-blocked by Redis. Production fails closed: when revocation
    state is unknown, the token is treated as revoked.
    """
    r = await _get_redis()
    if r is None:
        if revocation_checks_fail_closed():
            logger.error("is_revoked: Redis unavailable, fail-closed (jti=%s)", jti)
            return True
        logger.warning("is_revoked: Redis unavailable, fail-open outside production (jti=%s)", jti)
        return False
    try:
        return await r.exists(f"{_REVOKE_PREFIX}{jti}") > 0
    except Exception as e:
        if revocation_checks_fail_closed():
            logger.error("is_revoked: Redis error, fail-closed: %s (jti=%s)", e, jti)
            return True
        logger.warning("is_revoked: Redis error, fail-open outside production: %s (jti=%s)", e, jti)
        return False
    finally:
        await r.aclose()
