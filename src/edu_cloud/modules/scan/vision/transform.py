import cv2
import numpy as np


def compute_affine(
    src_anchors: list[dict],
    dst_anchors: list[dict],
) -> np.ndarray | None:
    """
    计算从 src（学生卷）到 dst（模版）的仿射变换矩阵。
    至少需要 3 个匹配点。有 4+ 点时用最小二乘拟合更稳健。
    """
    src_by_id = {a["id"]: a for a in src_anchors}
    dst_by_id = {a["id"]: a for a in dst_anchors}

    common_ids = sorted(set(src_by_id) & set(dst_by_id))
    if len(common_ids) < 3:
        return None

    priority = ["TL", "TR", "BL", "BR"]
    selected = [cid for cid in priority if cid in common_ids]

    src_pts = np.float32([[src_by_id[cid]["cx"], src_by_id[cid]["cy"]] for cid in selected])
    dst_pts = np.float32([[dst_by_id[cid]["cx"], dst_by_id[cid]["cy"]] for cid in selected])

    if len(selected) >= 4:
        matrix, _ = cv2.estimateAffinePartial2D(src_pts, dst_pts)
        return matrix
    else:
        return cv2.getAffineTransform(src_pts[:3], dst_pts[:3])


def transform_rect(
    matrix: np.ndarray,
    rect: dict,
) -> dict:
    """
    用仿射矩阵的逆变换将模版坐标映射回学生卷坐标。
    rect: {"x1", "y1", "x2", "y2"}
    """
    M_inv = cv2.invertAffineTransform(matrix)

    pts = np.float32([
        [rect["x1"], rect["y1"]],
        [rect["x2"], rect["y2"]],
    ]).reshape(-1, 1, 2)

    transformed = cv2.transform(pts, M_inv).reshape(-1, 2)

    return {
        "x1": int(round(transformed[0][0])),
        "y1": int(round(transformed[0][1])),
        "x2": int(round(transformed[1][0])),
        "y2": int(round(transformed[1][1])),
    }
