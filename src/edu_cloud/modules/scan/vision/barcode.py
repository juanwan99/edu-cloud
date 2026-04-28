"""Code-128 条码识别模块，基于 pyzbar。

增强策略（2026-04-29）：
1. 模板坐标自动缩放 — 当扫描图尺寸与模板尺寸不同时，按比例换算裁切坐标
2. 多策略重试 — 灰度→二值化(OTSU)→放大→自适应阈值，逐级尝试
3. 格式校验 — 可选的 expected_pattern 正则校验，过滤误读
"""
from pathlib import Path
from PIL import Image
from pyzbar.pyzbar import decode
import logging
import re

import cv2
import numpy as np

logger = logging.getLogger(__name__)

# 裁切区域在模板坐标上的额外边距（像素），防止条码紧贴边界被截断
_CROP_PAD = 80


def read_barcode(
    image_path: Path,
    crop_region: dict | None = None,
    template_size: dict | None = None,
    expected_pattern: str | None = None,
) -> str | None:
    """读取图片中的 Code-128 条码。

    Args:
        image_path: 图片文件路径
        crop_region: 裁切区域 {"x1", "y1", "x2", "y2"}（**模板坐标系**）
        template_size: 模板尺寸 {"width", "height"}，用于坐标缩放。
            当图片尺寸与模板不同时，crop_region 会按比例换算到图片坐标。
        expected_pattern: 可选正则表达式（如 r"^\\d{6}$"），不匹配的结果视为误读，
            返回 None 并记录 warning。

    Returns:
        条码内容字符串，识别失败返回 None
    """
    try:
        img = Image.open(image_path)
    except Exception as e:
        logger.warning("Cannot open image %s: %s", image_path, e)
        return None

    img_w, img_h = img.size

    if crop_region:
        try:
            scaled_crop = _scale_crop_region(
                crop_region, img_w, img_h, template_size,
            )
            img = img.crop((
                scaled_crop["x1"], scaled_crop["y1"],
                scaled_crop["x2"], scaled_crop["y2"],
            ))
        except (KeyError, TypeError) as e:
            logger.warning("Invalid crop_region %s: %s", crop_region, e)
            return None

    result = _decode_with_retry(img, image_path)

    if not result and crop_region:
        full_img = Image.open(image_path)
        if full_img.mode != "L":
            full_img = full_img.convert("L")
        result = _decode_with_retry(full_img, image_path)
        if result:
            logger.info("Barcode found (full-image fallback): %s", result)

    if result and expected_pattern:
        if not re.match(expected_pattern, result):
            logger.warning(
                "barcode_format_mismatch: file=%s, value=%s, expected=%s",
                image_path.name, result, expected_pattern,
            )
            return None

    return result


def _scale_crop_region(
    crop_region: dict,
    img_w: int,
    img_h: int,
    template_size: dict | None,
) -> dict:
    """将模板坐标系的 crop_region 缩放到实际图片坐标，附加 pad 边距。"""
    sx, sy = 1.0, 1.0
    if template_size:
        tpl_w = template_size.get("width", img_w)
        tpl_h = template_size.get("height", img_h)
        if tpl_w > 0:
            sx = img_w / tpl_w
        if tpl_h > 0:
            sy = img_h / tpl_h

    return {
        "x1": max(0, int(crop_region["x1"] * sx) - _CROP_PAD),
        "y1": max(0, int(crop_region["y1"] * sy) - _CROP_PAD),
        "x2": min(img_w, int(crop_region["x2"] * sx) + _CROP_PAD),
        "y2": min(img_h, int(crop_region["y2"] * sy) + _CROP_PAD),
    }


def _decode_with_retry(img: Image.Image, image_path: Path) -> str | None:
    """多策略尝试解码条码，逐级增强直到成功。

    策略顺序（按计算成本递增）：
    1. 灰度直接 decode
    2. OTSU 二值化
    3. 放大 2x + OTSU
    4. 放大 2x + 自适应阈值
    """
    # 转灰度
    if img.mode != "L":
        gray = img.convert("L")
    else:
        gray = img

    # --- 策略 1: 灰度直接 decode ---
    results = decode(gray)
    if results:
        text = results[0].data.decode("utf-8", errors="replace")
        logger.info("Barcode found: %s (type: %s)", text, results[0].type)
        return text

    # --- 策略 2: OTSU 二值化 ---
    gray_np = np.array(gray)
    _, binary = cv2.threshold(gray_np, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    results = decode(Image.fromarray(binary))
    if results:
        text = results[0].data.decode("utf-8", errors="replace")
        logger.info(
            "Barcode found (otsu): %s (type: %s)", text, results[0].type,
        )
        return text

    # --- 策略 3: 放大 2x + OTSU ---
    resized = cv2.resize(gray_np, None, fx=2, fy=2, interpolation=cv2.INTER_CUBIC)
    _, resized_binary = cv2.threshold(
        resized, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU,
    )
    results = decode(Image.fromarray(resized_binary))
    if results:
        text = results[0].data.decode("utf-8", errors="replace")
        logger.info(
            "Barcode found (resize+otsu): %s (type: %s)", text, results[0].type,
        )
        return text

    # --- 策略 4: 放大 2x + 自适应阈值 ---
    adaptive = cv2.adaptiveThreshold(
        resized, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 51, 10,
    )
    results = decode(Image.fromarray(adaptive))
    if results:
        text = results[0].data.decode("utf-8", errors="replace")
        logger.info(
            "Barcode found (resize+adaptive): %s (type: %s)",
            text, results[0].type,
        )
        return text

    logger.debug("No barcode found in %s after all retries", image_path)
    return None
