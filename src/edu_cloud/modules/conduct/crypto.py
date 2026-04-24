"""AES-256-GCM 加密 -- 用于学生身份证号、验证码等 PII 字段"""

import base64
import hashlib
import os
import logging

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from edu_cloud.config import settings

logger = logging.getLogger(__name__)

_KEY: bytes | None = None


_INSECURE_DEFAULTS = {"", "change-me-in-production", "default-dev-key"}


def _get_key() -> bytes:
    global _KEY
    if _KEY is None:
        raw = getattr(settings, "ENCRYPTION_KEY", "") or ""
        if raw in _INSECURE_DEFAULTS:
            logger.warning(
                "ENCRYPTION_KEY using insecure default — "
                "set a real key in .env for production!"
            )
            raw = "dev-only-insecure-key-do-not-use-in-production"
        _KEY = hashlib.sha256(raw.encode()).digest()
    return _KEY


def encrypt(plaintext: str | None) -> str | None:
    if not plaintext:
        return None
    key = _get_key()
    nonce = os.urandom(12)
    aesgcm = AESGCM(key)
    ct = aesgcm.encrypt(nonce, plaintext.encode("utf-8"), None)
    return base64.b64encode(nonce + ct).decode("ascii")


def decrypt(ciphertext: str | None) -> str | None:
    if not ciphertext:
        return None
    try:
        raw = base64.b64decode(ciphertext)
        nonce, ct = raw[:12], raw[12:]
        aesgcm = AESGCM(_get_key())
        return aesgcm.decrypt(nonce, ct, None).decode("utf-8")
    except Exception:
        logger.warning("conduct.crypto: decrypt failed")
        return None
