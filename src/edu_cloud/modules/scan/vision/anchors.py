import cv2
import numpy as np


def detect_anchors(
    gray: np.ndarray,
    min_area: int = 800,
    max_area: int = 8000,
    aspect_range: tuple[float, float] = (0.5, 2.5),
) -> list[dict]:
    """
    检测试卷四角定位点。

    Args:
        gray: 灰度图像 (H, W)
        min_area: 定位点最小面积
        max_area: 定位点最大面积
        aspect_range: 长宽比范围

    Returns:
        list of {"id": "TL"|"TR"|"BL"|"BR", "cx", "cy", "x", "y", "w", "h"}
    """
    if len(gray.shape) == 3:
        gray = cv2.cvtColor(gray, cv2.COLOR_BGR2GRAY)

    # 二值化（黑底白字反转，让定位点为白色前景）
    _, binary = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)

    contours, _ = cv2.findContours(binary, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    candidates = []
    for cnt in contours:
        area = cv2.contourArea(cnt)
        if area < min_area or area > max_area:
            continue
        x, y, w, h = cv2.boundingRect(cnt)
        aspect = w / h if h > 0 else 0
        if not (aspect_range[0] <= aspect <= aspect_range[1]):
            continue
        # 矩形度检查
        rect_fill = area / (w * h) if w * h > 0 else 0
        if rect_fill < 0.6:
            continue
        cx, cy = x + w // 2, y + h // 2
        candidates.append({"cx": cx, "cy": cy, "x": x, "y": y, "w": w, "h": h})

    if len(candidates) < 4:
        return candidates

    # 分类：按到四角的距离
    h_img, w_img = gray.shape[:2]
    corners = {
        "TL": (0, 0),
        "TR": (w_img, 0),
        "BL": (0, h_img),
        "BR": (w_img, h_img),
    }

    result = []
    used = set()
    for corner_id, (corner_x, corner_y) in corners.items():
        best_idx = -1
        best_dist = float("inf")
        for i, c in enumerate(candidates):
            if i in used:
                continue
            dist = ((c["cx"] - corner_x) ** 2 + (c["cy"] - corner_y) ** 2) ** 0.5
            if dist < best_dist:
                best_dist = dist
                best_idx = i
        if best_idx >= 0:
            used.add(best_idx)
            anchor = {**candidates[best_idx], "id": corner_id}
            result.append(anchor)

    return result
