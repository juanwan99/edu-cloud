"""端到端集成测试：作答 → BKT → 路径 → ���题"""
import pytest
from edu_cloud.modules.adaptive.bkt_engine import bkt_update, classify_da_state, BktParams
from edu_cloud.modules.adaptive.path_planner import plan_learning_path, topological_sort_dag
from edu_cloud.modules.adaptive.question_selector import select_transfer_band, filter_candidates


def test_full_pipeline_single_student():
    """模拟单学生 5 次作答后的完整诊断+推荐流程"""
    params = BktParams()

    # 模拟 3 个 DA 的作答历史
    da_mastery = {"da1": 0.1, "da2": 0.1, "da3": 0.1}

    # da1: 答对 3 次 → 应该提升到 fragile 或更高
    for _ in range(3):
        da_mastery["da1"] = bkt_update(da_mastery["da1"], True, params)

    # da2: 答错 2 次 → 应该仍然 weak
    for _ in range(2):
        da_mastery["da2"] = bkt_update(da_mastery["da2"], False, params)

    # 验证状态分类
    assert classify_da_state(da_mastery["da1"], 3) in ("fragile", "solid")
    assert classify_da_state(da_mastery["da2"], 2) == "weak"

    # 构建 mastery_map
    mastery_map = {
        "da1": {"mastery": da_mastery["da1"], "state": classify_da_state(da_mastery["da1"], 3)},
        "da2": {"mastery": da_mastery["da2"], "state": classify_da_state(da_mastery["da2"], 2)},
    }

    # 路径规划
    da_to_su = {"da1": "su_advanced", "da2": "su_base"}
    su_prereqs = {"su_advanced": ["su_base"]}
    path = plan_learning_path(mastery_map, da_to_su, su_prereqs)

    # 验证：weak 的 da2(su_base) 应排在 da1(su_advanced) 前面
    if len(path) >= 2:
        su_ids = [p["study_unit_id"] for p in path]
        if "su_base" in su_ids and "su_advanced" in su_ids:
            assert su_ids.index("su_base") < su_ids.index("su_advanced")

    # 选题
    for item in path:
        band = select_transfer_band(item["state"])
        candidates = [
            {"id": f"q_{item['study_unit_id']}_1", "transfer_band": band, "da_id": item["da_ids"][0]},
            {"id": f"q_{item['study_unit_id']}_2", "transfer_band": "mid", "da_id": item["da_ids"][0]},
        ]
        selected = filter_candidates(candidates, target_band=band, limit=3)
        assert len(selected) >= 1


def test_bkt_convergence():
    """连续答对应该收敛到 solid"""
    params = BktParams()
    mastery = 0.1
    for _ in range(20):
        mastery = bkt_update(mastery, True, params)
    assert mastery > 0.9
    assert classify_da_state(mastery, 20) == "solid"


def test_bkt_decline():
    """连续答错应该保持 weak"""
    params = BktParams()
    mastery = 0.5
    for _ in range(10):
        mastery = bkt_update(mastery, False, params)
    assert mastery < 0.5
    assert classify_da_state(mastery, 10) == "weak"
