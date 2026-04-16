import pytest
from edu_cloud.modules.adaptive.question_selector import select_transfer_band, filter_candidates


def test_weak_selects_near():
    assert select_transfer_band("weak") == "near"

def test_fragile_selects_mid():
    assert select_transfer_band("fragile") == "mid"

def test_solid_selects_far():
    assert select_transfer_band("solid") == "far"

def test_unseen_selects_near():
    assert select_transfer_band("unseen") == "near"

def test_filter_candidates_by_band():
    """target band items come first, then fallback to adjacent"""
    items = [
        {"id": "q1", "transfer_band": "near", "da_id": "da1"},
        {"id": "q2", "transfer_band": "mid", "da_id": "da1"},
        {"id": "q3", "transfer_band": "far", "da_id": "da1"},
    ]
    result = filter_candidates(items, target_band="near", limit=5)
    # All 3 returned (limit=5), but near first
    assert result[0]["id"] == "q1"
    # With limit=1, only near
    result_1 = filter_candidates(items, target_band="near", limit=1)
    assert len(result_1) == 1
    assert result_1[0]["id"] == "q1"

def test_filter_candidates_respects_limit():
    items = [
        {"id": f"q{i}", "transfer_band": "near", "da_id": "da1"}
        for i in range(10)
    ]
    result = filter_candidates(items, target_band="near", limit=3)
    assert len(result) == 3

def test_filter_candidates_fallback_to_adjacent():
    """目标 band 无题时，取相邻 band"""
    items = [
        {"id": "q1", "transfer_band": "mid", "da_id": "da1"},
    ]
    result = filter_candidates(items, target_band="near", limit=3)
    assert len(result) == 1  # 降级到 mid
