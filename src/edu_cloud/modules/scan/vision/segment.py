from PIL import Image
from pathlib import Path
import numpy as np
import logging
from .anchors import detect_anchors
from .transform import compute_affine, transform_rect

logger = logging.getLogger(__name__)


def crop_region(img: Image.Image, rect: dict) -> Image.Image:
    """从 PIL 图像中裁切矩形区域"""
    x1 = max(0, rect["x1"])
    y1 = max(0, rect["y1"])
    x2 = min(img.width, rect["x2"])
    y2 = min(img.height, rect["y2"])
    return img.crop((x1, y1, x2, y2))


def segment_one_image(
    image_path: Path,
    template: dict,
    output_dir: Path,
    student_id: str,
) -> dict:
    """
    对单张学生图执行分割。

    Returns:
        {"student_id": str, "regions": {region_id: output_path}, "errors": [...]}
    """
    result = {"student_id": student_id, "regions": {}, "errors": []}

    # 用 PIL 读取（支持中文路径）
    try:
        pil_img = Image.open(image_path)
        if pil_img.mode == "P":
            pil_img = pil_img.convert("RGB")
        elif pil_img.mode == "L":
            pass  # grayscale ok for detection
        elif pil_img.mode not in ("RGB", "RGBA"):
            pil_img = pil_img.convert("RGB")
    except Exception as e:
        result["errors"].append(f"Cannot read: {image_path}: {e}")
        return result

    # 灰度用于定位点检测
    gray_img = pil_img.convert("L")
    gray = np.array(gray_img)

    # 检测学生卷定位点
    stu_anchors = detect_anchors(gray)
    tpl_anchors = template.get("anchors", [])

    # 计算仿射变换（如果有足够定位点）
    matrix = None
    if len(stu_anchors) >= 3 and len(tpl_anchors) >= 3:
        matrix = compute_affine(stu_anchors, tpl_anchors)

    # 确保裁切用 RGB
    if pil_img.mode not in ("RGB", "RGBA"):
        pil_img = pil_img.convert("RGB")

    for region in template.get("regions", []):
        rect = region["rect"]

        if matrix is not None:
            actual_rect = transform_rect(matrix, rect)
        else:
            actual_rect = rect

        try:
            cropped = crop_region(pil_img, actual_rect)
            region_dir = output_dir / region["id"]
            region_dir.mkdir(parents=True, exist_ok=True)
            out_path = region_dir / f"{student_id}.png"
            cropped.save(str(out_path))
            result["regions"][region["id"]] = str(out_path)
        except Exception as e:
            result["errors"].append(f"Region {region['id']}: {e}")

    return result


def segment_batch(
    image_dir: Path,
    side: str,
    template: dict,
    output_dir: Path,
    on_progress: callable = None,
) -> list[dict]:
    """
    批量切割一个科目指定面的所有学生图像。
    """
    files = sorted([
        f for f in image_dir.iterdir()
        if f.suffix.lower() in (".png", ".jpg", ".bmp") and f.stem.endswith(side)
    ])

    results = []
    for i, f in enumerate(files):
        student_id = f.stem[:-1]  # 去掉末尾的 A/B
        r = segment_one_image(f, template, output_dir, student_id)
        results.append(r)
        if on_progress:
            on_progress(i + 1, len(files))

    return results
