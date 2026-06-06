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


def test_frontend_passes_on_real(truth):
    assert cms.check_frontend(truth, REPO) == []


def test_frontend_route_drift_fails(truth):  # 反例 #4 routeAccess 漂移
    parsed = {"routeAccess": {"/exams": "grading"}, "router_meta": {}, "sidebar": {}, "dashboard": {}}
    errs = cms._compare_frontend(truth, parsed)
    assert any("/exams" in e for e in errs)


def test_frontend_meta_vs_routeaccess_inconsistent_fails(truth):  # 反例 #5
    parsed = {"routeAccess": {"/exams": "exam"}, "router_meta": {"/exams": "grading"}, "sidebar": {}, "dashboard": {}}
    errs = cms._compare_frontend(truth, parsed)
    # 硬断言（plan-review F3）：必须是同一路由在两个具名 surface 间的冲突，不接受任意含 "meta" 的消息
    assert any("/exams" in e and "routeAccess" in e and "router-meta" in e for e in errs), errs


def test_frontend_wild_value_fails(truth):  # 反例 #6 野值
    parsed = {"routeAccess": {}, "router_meta": {}, "sidebar": {"/x": "ghost"}, "dashboard": {"/y": "ghost2"}}
    errs = cms._compare_frontend(truth, parsed)
    assert any("ghost" in e for e in errs)


def test_frontend_undeclared_route_fails(truth):  # 反例 #15（F1）：未声明前端 route（fail-closed）
    parsed = {"routeAccess": {"/brand-new": "exam"}, "router_meta": {}, "sidebar": {}, "dashboard": {}}
    errs = cms._compare_frontend(truth, parsed)
    assert any("/brand-new" in e and "fail-closed" in e for e in errs)


def test_frontend_sidebar_mismatch_fails(truth):  # 反例 #16（F1）：sidebar 错配到另一合法值
    parsed = {"routeAccess": {}, "router_meta": {}, "sidebar": {"/exams": "grading"}, "dashboard": {}}
    errs = cms._compare_frontend(truth, parsed)
    assert any("/exams" in e and "不一致" in e for e in errs)


def test_frontend_dashboard_route_mismatch_fails(truth):  # 反例 #17（必修③）：dashboard route 错配到另一合法值
    # /homework 真源=homework，dashboard 给合法值 grading → route 已声明(fail-closed 通过)但值不一致 → 红
    parsed = {"routeAccess": {}, "router_meta": {}, "sidebar": {}, "dashboard": {"/homework": "grading"}}
    errs = cms._compare_frontend(truth, parsed)
    assert any("/homework" in e and "dashboard" in e and "不一致" in e for e in errs), errs


def test_frontend_null_route_with_code_fails(truth):  # 反例 #19（R5 F-002）：null route 被加合法 moduleCode
    # /students 真源=null（不受门控），被错误加 moduleCode=exam → 红（不应 gating）
    parsed = {"routeAccess": {"/students": "exam"}, "router_meta": {}, "sidebar": {}, "dashboard": {}}
    errs = cms._compare_frontend(truth, parsed)
    assert any("/students" in e and "null" in e for e in errs), errs


def test_frontend_router_meta_dynamic_route_drift_fails(truth):  # 反例 #21（R5 F-001）：动态路由纳入分母后漂移可抓
    # /exams/:id 真源=exam，router_meta 给 grading → fail-closed 通过(in fr)但值不一致 → 红
    parsed = {"routeAccess": {}, "router_meta": {"/exams/:id": "grading"}, "sidebar": {}, "dashboard": {}}
    errs = cms._compare_frontend(truth, parsed)
    assert any("/exams/:id" in e and "不一致" in e for e in errs), errs


def test_portal_passes_on_real(truth):
    assert cms.check_portal(truth, REPO) == []


def test_portal_service_module_mismatch_fails(truth):  # 反例 #7
    errs = cms._compare_portal(truth, [{"id": "exam", "module_code": "grading"}])
    assert any("exam" in e for e in errs)


def test_portal_service_wild_value_fails(truth):  # 反例 #7 野值
    errs = cms._compare_portal(truth, [{"id": "x", "module_code": "ghost"}])
    assert any("ghost" in e for e in errs)


def test_known_drift_orphan_fails(truth):  # 反例 #10 孤儿
    bad = copy.deepcopy(truth)
    bad["known_drift"].append({"id": "orphan-xyz", "consumer": "backend_middleware",
                               "locus": "/api/v1/nope", "expect": "x", "actual": "y", "severity": "low"})
    errs = cms.check_known_drift(bad, REPO)
    assert any("orphan-xyz" in e for e in errs)


def test_frontend_drift_no_probe_fails(truth):  # 反例 #13a（F2）：frontend drift 无探测器 → fail-closed
    bad = copy.deepcopy(truth)
    bad["known_drift"].append({"id": "ghost-frontend-drift", "consumer": "frontend",
                               "locus": "/x", "expect": "a", "actual": "b", "severity": "low"})
    errs = cms.check_known_drift(bad, REPO)
    assert any("ghost-frontend-drift" in e for e in errs)


def test_frontend_drift_probe_detects_fix(truth):  # 反例 #13b（F2）：studio 实际已 present → drift 探测为「不成立」
    present = {"routeAccess": {"/studio": "studio"}, "router_meta": {}, "sidebar": {}, "dashboard": {}}
    assert cms._FRONTEND_DRIFT_PROBES["studio-frontend-entry-missing"]["still_holds"](present) is False
    absent = {"routeAccess": {}, "router_meta": {}, "sidebar": {}, "dashboard": {}}
    assert cms._FRONTEND_DRIFT_PROBES["studio-frontend-entry-missing"]["still_holds"](absent) is True


def test_frontend_drift_tuple_mismatch_fails(truth):  # 反例 #20（R5 F-003）：frontend drift expect/actual 篡改
    bad = copy.deepcopy(truth)
    for d in bad["known_drift"]:
        if d["id"] == "studio-frontend-entry-missing":
            d["actual"] = "present"  # 篡改登记 actual，与 probe 契约(absent)不符 → 四元组失配红
    errs = cms.check_frontend_drift(bad, REPO)
    assert any("studio-frontend-entry-missing" in e and "F-003" in e for e in errs), errs
