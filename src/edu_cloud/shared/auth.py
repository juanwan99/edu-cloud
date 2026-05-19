from datetime import datetime, timedelta, timezone
from uuid import uuid4
import jwt
from edu_cloud.config import settings


def create_access_token(data: dict) -> str:
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode["exp"] = expire
    to_encode.setdefault("jti", uuid4().hex)
    return jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


def decode_token(token: str) -> dict:
    return jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])


IMPERSONATION_EXPIRE_MINUTES = 30


def create_impersonation_token(
    *,
    impersonator_id: str,
    effective_role: str,
    effective_school_id: str,
    scope_override: dict,
) -> str:
    """Create a short-lived JWT for role impersonation.

    NOTE: grants full permissions of effective_role — may be restricted
    to read-only in a future iteration.
    """
    expire = datetime.now(timezone.utc) + timedelta(minutes=IMPERSONATION_EXPIRE_MINUTES)
    payload = {
        "sub": impersonator_id,
        "is_impersonation": True,
        "impersonator_id": impersonator_id,
        "effective_role": effective_role,
        "effective_school_id": effective_school_id,
        "scope_override": scope_override,
        "exp": expire,
        "jti": uuid4().hex,
    }
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
