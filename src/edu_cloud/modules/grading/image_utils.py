"""图片预处理工具 — 控制分辨率以优化 LLM token 消耗。

Gemini 按 768×768 tile 计费，每 tile = 258 tokens。
确保单题答卷图片不超过 1 tile，节省图片 token 费用。
"""
from __future__ import annotations

import io
import logging
from PIL import Image

logger = logging.getLogger(__name__)

MAX_DIMENSION = 768


def resize_image_for_llm(image_bytes: bytes, max_dim: int = MAX_DIMENSION) -> bytes:
    """缩放图片使最大边不超过 max_dim，返回 JPEG bytes。

    如果图片已经在限制内，直接返回原始 bytes（避免重新编码损失）。
    """
    img = Image.open(io.BytesIO(image_bytes))
    w, h = img.size

    if w <= max_dim and h <= max_dim:
        return image_bytes

    scale = max_dim / max(w, h)
    new_w = int(w * scale)
    new_h = int(h * scale)

    img = img.resize((new_w, new_h), Image.LANCZOS)
    if img.mode == "RGBA":
        img = img.convert("RGB")

    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=85)
    result = buf.getvalue()

    logger.debug(
        "resize_image_for_llm: %dx%d → %dx%d, %d → %d bytes",
        w, h, new_w, new_h, len(image_bytes), len(result),
    )
    return result
