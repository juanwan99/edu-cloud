"""分数段计算（硬编码默认阈值，不再支持学校自定义配置）。"""

DEFAULT_BOUNDARIES = [85, 70, 60]
DEFAULT_LABELS = ["优秀", "良好", "及格", "不及格"]


def compute_segments(
    scores: list[float],
    max_score: float,
    boundaries: list[int],
    labels: list[str],
) -> list[dict]:
    """将原始分按百分比阈值分段。

    boundaries 降序，如 [85, 70, 60]。labels 比 boundaries 多一个。
    返回 [{label, count, percentage, boundary_min, boundary_max}]。
    """
    n = len(scores)
    segments = []
    sorted_boundaries = sorted(boundaries, reverse=True)

    if not sorted_boundaries:
        return [{
            "label": labels[0] if labels else "全部",
            "count": n,
            "percentage": 1.0 if n > 0 else 0,
            "boundary_min": 0,
            "boundary_max": 101,
        }]

    for i, label in enumerate(labels):
        if i == 0:
            b_min = sorted_boundaries[0]
            b_max = 101
        elif i < len(sorted_boundaries):
            b_min = sorted_boundaries[i]
            b_max = sorted_boundaries[i - 1]
        else:
            b_min = 0
            b_max = sorted_boundaries[-1] if sorted_boundaries else 101

        count = 0
        for score in scores:
            pct = (score / max_score * 100) if max_score > 0 else 0
            if b_min <= pct < b_max:
                count += 1
            elif i == 0 and pct >= b_min:
                count += 1

        segments.append({
            "label": label,
            "count": count,
            "percentage": round(count / n, 4) if n > 0 else 0,
            "boundary_min": b_min,
            "boundary_max": b_max,
        })

    return segments


async def get_segment_config(
    db, school_id: str, subject_code: str | None = None,
) -> tuple[list[int], list[str]]:
    """返回硬编码默认分数段配置（db 参数保留以兼容调用方签名）。"""
    return DEFAULT_BOUNDARIES, DEFAULT_LABELS
