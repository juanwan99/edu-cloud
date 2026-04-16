import pytest
from edu_cloud.modules.adaptive.bkt_engine import bkt_update, BktParams


def test_bkt_update_correct_increases_mastery():
    params = BktParams(p_init=0.1, p_transit=0.2, p_guess=0.25, p_slip=0.1)
    old_mastery = 0.3
    new_mastery = bkt_update(old_mastery, is_correct=True, params=params)
    assert new_mastery > old_mastery
    assert 0.0 <= new_mastery <= 1.0


def test_bkt_update_incorrect_decreases_mastery():
    params = BktParams(p_init=0.1, p_transit=0.2, p_guess=0.25, p_slip=0.1)
    old_mastery = 0.7
    new_mastery = bkt_update(old_mastery, is_correct=False, params=params)
    assert new_mastery < old_mastery
    assert 0.0 <= new_mastery <= 1.0


def test_bkt_update_high_mastery_correct_stays_high():
    params = BktParams(p_init=0.1, p_transit=0.2, p_guess=0.25, p_slip=0.1)
    new_mastery = bkt_update(0.95, is_correct=True, params=params)
    assert new_mastery > 0.95


def test_bkt_update_low_mastery_incorrect_posterior_low():
    """Low mastery + incorrect: posterior drops, but learning transfer adds some."""
    params = BktParams(p_init=0.1, p_transit=0.2, p_guess=0.25, p_slip=0.1)
    new_mastery = bkt_update(0.05, is_correct=False, params=params)
    # Posterior ~0.007, but transit pushes to ~0.206. Still lower than 0.3
    assert new_mastery < 0.3


def test_bkt_classify_state():
    from edu_cloud.modules.adaptive.bkt_engine import classify_da_state
    assert classify_da_state(mastery=0.0, attempts=0) == "unseen"
    assert classify_da_state(mastery=0.3, attempts=5) == "weak"
    assert classify_da_state(mastery=0.6, attempts=10) == "fragile"
    assert classify_da_state(mastery=0.85, attempts=15) == "solid"


def test_bkt_update_with_zero_mastery():
    params = BktParams(p_init=0.1, p_transit=0.2, p_guess=0.25, p_slip=0.1)
    new_mastery = bkt_update(0.0, is_correct=True, params=params)
    assert new_mastery > 0.0


def test_bkt_update_with_near_one_mastery():
    """Near-1.0 mastery + incorrect should decrease."""
    params = BktParams(p_init=0.1, p_transit=0.2, p_guess=0.25, p_slip=0.1)
    new_mastery = bkt_update(0.99, is_correct=False, params=params)
    assert new_mastery < 0.99
