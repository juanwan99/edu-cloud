import cv2
import numpy as np


def detect_lines(
    gray: np.ndarray,
    min_width_ratio: float = 0.4,
    wide_threshold: int = 2400,
) -> list[dict]:
    """检测水平分割线。宽幅A3图自动分半。"""
    if len(gray.shape) == 3:
        gray = cv2.cvtColor(gray, cv2.COLOR_BGR2GRAY)
    h_img, w_img = gray.shape
    if w_img > wide_threshold:
        mid = w_img // 2
        return (_detect_region(gray[:, :mid], min_width_ratio, 0, 0)
              + _detect_region(gray[:, mid:], min_width_ratio, 1, mid))
    return _detect_region(gray, min_width_ratio, 0, 0)


def _detect_region(gray, min_width_ratio, page, x_offset):
    h, w = gray.shape
    _, binary = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (max(w // 3, 100), 1))
    mask = cv2.morphologyEx(binary, cv2.MORPH_OPEN, kernel)
    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    lines = []
    for cnt in contours:
        x, y, cw, ch = cv2.boundingRect(cnt)
        if cw >= w * min_width_ratio:
            lines.append({"y": y + ch // 2, "x1": x + x_offset, "x2": x + cw + x_offset, "width": cw, "page": page})
    lines.sort(key=lambda l: l["y"])
    return lines
