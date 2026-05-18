"""分数段计算逻辑测试（配置 CRUD 已删除，只保留 compute + 硬编码默认值验证）。"""
from edu_cloud.modules.analytics.segment_service import (
    compute_segments, get_segment_config,
    DEFAULT_BOUNDARIES, DEFAULT_LABELS,
)


def test_compute_segments_default():
    scores = [95, 82, 73, 65, 50, 88, 40]
    result = compute_segments(
        scores=scores, max_score=100.0,
        boundaries=[85, 70, 60], labels=["优秀", "良好", "及格", "不及格"],
    )
    assert len(result) == 4
    excellent = next(s for s in result if s["label"] == "优秀")
    assert excellent["count"] == 2  # 95, 88
    poor = next(s for s in result if s["label"] == "不及格")
    assert poor["count"] == 2  # 50, 40


def test_compute_segments_empty():
    result = compute_segments(scores=[], max_score=100.0, boundaries=[85, 70, 60], labels=["优秀", "良好", "及格", "不及格"])
    assert all(s["count"] == 0 for s in result)


def test_compute_segments_empty_boundaries():
    result = compute_segments(scores=[80, 90], max_score=100.0, boundaries=[], labels=["全部"])
    assert len(result) == 1
    assert result[0]["count"] == 2
    assert result[0]["label"] == "全部"


def test_compute_segments_max_score_zero():
    result = compute_segments(scores=[0, 0], max_score=0.0, boundaries=[85, 70, 60], labels=["优秀", "良好", "及格", "不及格"])
    assert result[-1]["count"] == 2


async def test_get_config_returns_hardcoded_defaults(db):
    b, l = await get_segment_config(db, "nonexistent_school")
    assert b == DEFAULT_BOUNDARIES
    assert l == DEFAULT_LABELS
