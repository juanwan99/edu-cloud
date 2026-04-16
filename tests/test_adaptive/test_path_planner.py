import pytest
from edu_cloud.modules.adaptive.path_planner import (
    topological_sort_dag, compute_gap_scores, plan_learning_path,
)


def test_topological_sort_simple_chain():
    """A → B → C 应该排序为 [A, B, C]"""
    nodes = ["A", "B", "C"]
    edges = {"B": ["A"], "C": ["B"]}
    result = topological_sort_dag(nodes, edges)
    assert result.index("A") < result.index("B") < result.index("C")


def test_topological_sort_diamond():
    """A → B, A → C, B → D, C → D"""
    nodes = ["A", "B", "C", "D"]
    edges = {"B": ["A"], "C": ["A"], "D": ["B", "C"]}
    result = topological_sort_dag(nodes, edges)
    assert result.index("A") < result.index("B")
    assert result.index("A") < result.index("C")
    assert result.index("B") < result.index("D")
    assert result.index("C") < result.index("D")


def test_compute_gap_scores():
    """weak DA 的 gap score 应高于 fragile"""
    mastery_map = {
        "da1": {"mastery": 0.3, "state": "weak"},
        "da2": {"mastery": 0.6, "state": "fragile"},
        "da3": {"mastery": 0.9, "state": "solid"},
    }
    scores = compute_gap_scores(mastery_map)
    assert scores["da1"] > scores["da2"]
    assert scores["da3"] == 0.0


def test_plan_learning_path_skips_solid():
    """solid 的 DA 应被跳过"""
    mastery_map = {
        "da1": {"mastery": 0.3, "state": "weak"},
        "da2": {"mastery": 0.9, "state": "solid"},
    }
    da_to_su = {"da1": "su1", "da2": "su2"}
    su_prereqs = {}
    path = plan_learning_path(mastery_map, da_to_su, su_prereqs)
    su_ids = [item["study_unit_id"] for item in path]
    assert "su1" in su_ids
    assert "su2" not in su_ids


def test_plan_learning_path_prerequisite_first():
    """前置 SU 排在依赖 SU 之前"""
    mastery_map = {
        "da1": {"mastery": 0.3, "state": "weak"},
        "da2": {"mastery": 0.4, "state": "weak"},
    }
    da_to_su = {"da1": "su_base", "da2": "su_advanced"}
    su_prereqs = {"su_advanced": ["su_base"]}
    path = plan_learning_path(mastery_map, da_to_su, su_prereqs)
    su_ids = [item["study_unit_id"] for item in path]
    assert su_ids.index("su_base") < su_ids.index("su_advanced")


def test_plan_learning_path_same_layer_sorted_by_gap():
    """同��� SU 按 gap_score 降序"""
    mastery_map = {
        "da1": {"mastery": 0.2, "state": "weak"},   # gap=0.8
        "da2": {"mastery": 0.7, "state": "fragile"}, # gap=0.3
        "da3": {"mastery": 0.4, "state": "weak"},   # gap=0.6
    }
    # All at same layer (no prerequisites)
    da_to_su = {"da1": "su_high", "da2": "su_low", "da3": "su_mid"}
    su_prereqs = {}
    path = plan_learning_path(mastery_map, da_to_su, su_prereqs)
    su_ids = [item["study_unit_id"] for item in path]
    # su_high(0.8) > su_mid(0.6) > su_low(0.3)
    assert su_ids == ["su_high", "su_mid", "su_low"]
