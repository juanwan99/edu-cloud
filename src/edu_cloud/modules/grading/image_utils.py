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


_BLANK_INK_THRESHOLD = 0.003


def is_blank_image_cv(image_bytes: bytes) -> bool:
    """CV 空白检测：墨迹率 < 0.3% 判定为空白卷。去除格线后纯手写墨迹极少。"""
    import cv2
    import numpy as np

    arr = np.frombuffer(image_bytes, dtype=np.uint8)
    img = cv2.imdecode(arr, cv2.IMREAD_GRAYSCALE)
    if img is None:
        return False
    h, w = img.shape

    _, binary = cv2.threshold(img, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)

    hk = cv2.getStructuringElement(cv2.MORPH_RECT, (max(w // 20, 1), 1))
    vk = cv2.getStructuringElement(cv2.MORPH_RECT, (1, max(h // 15, 1)))
    binary = cv2.subtract(binary, cv2.morphologyEx(binary, cv2.MORPH_OPEN, hk))
    binary = cv2.subtract(binary, cv2.morphologyEx(binary, cv2.MORPH_OPEN, vk))

    ratio = np.count_nonzero(binary) / binary.size
    return ratio < _BLANK_INK_THRESHOLD


_INK_COEFF = 7000


def estimate_char_count_cv(image_bytes: bytes) -> int:
    """用墨迹面积比估算手写字数（去格线后）。精度 ±15%，用于校验 LLM OCR 是否丢页。"""
    import cv2
    import numpy as np

    arr = np.frombuffer(image_bytes, dtype=np.uint8)
    img = cv2.imdecode(arr, cv2.IMREAD_GRAYSCALE)
    if img is None:
        return 0
    h, w = img.shape

    _, binary = cv2.threshold(img, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)

    hk = cv2.getStructuringElement(cv2.MORPH_RECT, (w // 20, 1))
    vk = cv2.getStructuringElement(cv2.MORPH_RECT, (1, h // 15))
    binary = cv2.subtract(binary, cv2.morphologyEx(binary, cv2.MORPH_OPEN, hk))
    binary = cv2.subtract(binary, cv2.morphologyEx(binary, cv2.MORPH_OPEN, vk))

    ratio = np.count_nonzero(binary) / binary.size
    return int(ratio * _INK_COEFF)
