"""Token revocation store backed by Redis.

Revoked JTIs are stored in a Redis SET with TTL matching token expiry.
Fail-open: if Redis is unavailable, revocation checks are skipped.
"""
import logging
from edu_cloud.config import settings

logger = logging.getLogger(__name__)

_REVOKE_PREFIX = "revoked_jti:"


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
    """Check if a JTI has been revoked. Fail-open on Redis errors."""
    r = await _get_redis()
    if r is None:
        return False
    try:
        return await r.exists(f"{_REVOKE_PREFIX}{jti}") > 0
    except Exception:
        return False
    finally:
        await r.aclose()
