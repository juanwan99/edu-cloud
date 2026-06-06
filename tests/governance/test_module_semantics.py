from pathlib import Path
import copy
import pytest
from scripts.governance import check_module_semantics as cms

REPO = Path(__file__).resolve().parents[2]


@pytest.fixture
def truth():
    return cms.load_truth(REPO / "docs/governance/module-semantics.yaml")


def test_self_consistency_passes_on_real_truth(truth):
    assert cms.check_self_consistency(truth, REPO) == []


def test_layer1_mismatch_with_module_codes_fails(truth):  # 反例 #8
    bad = copy.deepcopy(truth)
    bad["school_module_codes"].append("ghost_module")
    errs = cms.check_self_consistency(bad, REPO)
    assert any("school_module_codes" in e for e in errs)


def test_layer2_missing_arch_module_fails(truth):  # 反例 #9
    bad = copy.deepcopy(truth)
    del bad["architecture_to_module_code"]["scan"]
    errs = cms.check_self_consistency(bad, REPO)
    assert any("architecture_to_module_code" in e and "scan" in e for e in errs)


def test_backend_passes_on_real(truth):
    assert cms.check_backend(truth, REPO) == []


def test_backend_unregistered_drift_id_fails(truth):  # 反例 #1 假修复
    bad = copy.deepcopy(truth)
    bad["known_drift"] = [d for d in bad["known_drift"] if d["id"] != "conduct-backend-fail-open"]
    errs = cms.check_backend(bad, REPO)
    assert any("/api/v1/conduct" in e for e in errs)


def test_backend_new_passthrough_prefix_fails(truth):  # 反例 #2 fail-closed
    discovered = {"/api/v1/exams": "gated:exam", "/api/v1/newthing": "pass-through"}
    errs = cms._compare_backend(truth, discovered)
    assert any("/api/v1/newthing" in e for e in errs)


def test_backend_mismatch_mapping_fails(truth):  # 反例 #3 错配
    discovered = {"/api/v1/analytics": "gated:exam"}  # 真源期望 study_analytics
    errs = cms._compare_backend(truth, discovered)
    assert any("/api/v1/analytics" in e for e in errs)


def test_backend_route_discovery_covers_decorator(truth):  # 反例 #11 base-prefix+decorator
    prefixes = cms.discover_backend_prefixes(REPO)
    assert "/api/v1/grades" in prefixes
    assert "/api/v1/teachers" in prefixes


def test_backend_drift_tuple_mismatch_fails(truth):  # 反例 #12 元组漂移
    bad = copy.deepcopy(truth)
    for d in bad["known_drift"]:
        if d["id"] == "conduct-backend-fail-open":
            d["actual"] = "gated:conduct"  # 谎称已修，但实际仍 pass-through
    errs = cms.check_backend(bad, REPO)
    assert any("conduct-backend-fail-open" in e for e in errs)


def test_backend_stale_truth_prefix_fails(truth):  # 反例 #14（F2）：真源声明但 discovery 未发现
    discovered = {"/api/v1/grades": "pass-through"}  # 只发现一个，真源其余皆 stale
    errs = cms._compare_backend(truth, discovered)
    assert any("/api/v1/exams" in e and "未被 route discovery 发现" in e for e in errs)


def test_backend_fixed_but_drift_retained_fails(truth):  # 反例 #18（R4 F-001）：实际已修复但 drift 仍保留
    # academic 实际已修复：actual == expect == gated:teaching，但 backend_routes 仍挂 drift 字段 → stale drift 红
    discovered = {"/api/v1/academic": "gated:teaching"}
    errs = cms._compare_backend(truth, discovered)
    assert any("/api/v1/academic" in e and "仍登记 drift" in e for e in errs), errs
