"""扫描视觉处理模块 — 从 paper-seg 迁入。"""
from .anchors import detect_anchors
from .transform import compute_affine, transform_rect
from .segment import crop_region
from .barcode import read_barcode
from .fillmark import recognize_page, recognize_choice_group
from .lines import detect_lines

__all__ = [
    "detect_anchors", "compute_affine", "transform_rect",
    "crop_region", "read_barcode", "recognize_page", "recognize_choice_group",
    "detect_lines",
]
