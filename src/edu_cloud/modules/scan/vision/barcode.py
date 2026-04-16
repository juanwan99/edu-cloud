"""Code-128 条码识别模块，基于 pyzbar。"""
from pathlib import Path
from PIL import Image
from pyzbar.pyzbar import decode
import logging

logger = logging.getLogger(__name__)


def read_barcode(
    image_path: Path,
    crop_region: dict | None = None,
) -> str | None:
    """
    读取图片中的 Code-128 条码。

    Args:
        image_path: 图片文件路径
        crop_region: 可选裁切区域 {"x1", "y1", "x2", "y2"}，只在该区域内识别

    Returns:
        条码内容字符串，识别失败返回 None
    """
    try:
        img = Image.open(image_path)
    except Exception as e:
        logger.warning("Cannot open image %s: %s", image_path, e)
        return None

    if crop_region:
        try:
            img = img.crop((
                crop_region["x1"], crop_region["y1"],
                crop_region["x2"], crop_region["y2"],
            ))
        except (KeyError, TypeError) as e:
            logger.warning("Invalid crop_region %s: %s", crop_region, e)
            return None

    # 转灰度提高识别率
    if img.mode != "L":
        img = img.convert("L")

    results = decode(img)
    if results:
        barcode_text = results[0].data.decode("utf-8", errors="replace")
        logger.info("Barcode found: %s (type: %s)", barcode_text, results[0].type)
        return barcode_text

    logger.debug("No barcode found in %s", image_path)
    return None
