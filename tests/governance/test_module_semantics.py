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


def test_frontend_drift_locus_mismatch_fails(truth):  # 反例 #22（Task 5.1）：frontend drift locus 篡改 → 四元组失配红
    # 篡改 studio 的 locus，与 probe 契约(studio-entry)不符 → consumer,locus,expect,actual 四元组精确豁免要求报红
    bad = copy.deepcopy(truth)
    for d in bad["known_drift"]:
        if d["id"] == "studio-frontend-entry-missing":
            d["locus"] = "wrong-locus"  # 篡改登记 locus，与 probe 契约不符 → 四元组失配红
    errs = cms.check_frontend_drift(bad, REPO)
    assert any("studio-frontend-entry-missing" in e and "F-003" in e for e in errs), errs


# ===== codex-review F-001/F-002 修复：前端 fail-closed 缺口 =====
# F-001 反例：受控 route 在某 surface 露出但全部露出面均缺失 moduleCode → fail-open 缺口必须报红。
#   _surface_routes 携带每个 surface 实际出现的全部 route（含无 moduleCode 者）；旧格式 parsed（无此键）退化跳过。

def test_frontend_routeaccess_missing_modulecode_fails(truth):  # 反例 #23（F-001 HIGH）
    # /exams 真源=exam（受控），在 routeAccess 露出却无 moduleCode → fail-open，必须报红
    parsed = {"routeAccess": {}, "router_meta": {}, "sidebar": {}, "dashboard": {},
              "_surface_routes": {"routeAccess": {"/exams"}}}
    errs = cms._compare_frontend(truth, parsed)
    assert any("/exams" in e and "moduleCode" in e for e in errs), errs


def test_frontend_router_meta_missing_modulecode_fails(truth):  # 反例 #24（F-001 HIGH）
    parsed = {"routeAccess": {}, "router_meta": {}, "sidebar": {}, "dashboard": {},
              "_surface_routes": {"router_meta": {"/exams"}}}
    errs = cms._compare_frontend(truth, parsed)
    assert any("/exams" in e and "moduleCode" in e for e in errs), errs


def test_frontend_sidebar_missing_modulecode_fails(truth):  # 反例 #25（F-001 HIGH）
    parsed = {"routeAccess": {}, "router_meta": {}, "sidebar": {}, "dashboard": {},
              "_surface_routes": {"sidebar": {"/exams"}}}
    errs = cms._compare_frontend(truth, parsed)
    assert any("/exams" in e and "moduleCode" in e for e in errs), errs


def test_frontend_dashboard_missing_modulecode_fails(truth):  # 反例 #26（F-001 HIGH）
    # /homework 真源=homework（受控），在 dashboard 露出却无 moduleCode → 报红
    parsed = {"routeAccess": {}, "router_meta": {}, "sidebar": {}, "dashboard": {},
              "_surface_routes": {"dashboard": {"/homework"}}}
    errs = cms._compare_frontend(truth, parsed)
    assert any("/homework" in e and "moduleCode" in e for e in errs), errs


def test_frontend_null_route_missing_modulecode_passes(truth):  # 反例 #23b：null route 缺码不应报（本就不该 gating）
    # /students 真源=null，在 routeAccess 露出且无 moduleCode → 正确，不报红
    parsed = {"routeAccess": {}, "router_meta": {}, "sidebar": {}, "dashboard": {},
              "_surface_routes": {"routeAccess": {"/students"}}}
    errs = cms._compare_frontend(truth, parsed)
    assert not any("/students" in e and "moduleCode" in e for e in errs), errs


def test_frontend_double_quote_modulecode_parsed(truth):  # 反例 #27（F-002 MED）：双引号字面量须被解析并比对
    # 双引号写法 "/exams": { moduleCode: "conduct" } 须解析为 {/exams: conduct} 并因与真源 exam 不一致而报红
    pairs = cms._parse_route_module_pairs('"/exams": { permission: "view_exams", moduleCode: "conduct" }')
    assert pairs == {"/exams": "conduct"}, pairs
    parsed = {"routeAccess": pairs, "router_meta": {}, "sidebar": {}, "dashboard": {}}
    errs = cms._compare_frontend(truth, parsed)
    assert any("/exams" in e and "不一致" in e for e in errs), errs


# ===== R2 收口：门控面按 surface 独立 fail-closed（旧全局并集会被任一面的码掩盖 cross-surface 缺口）=====
# 门控面 = routeAccess（canAccessRouteForRole→moduleMatches）/ sidebar（按 moduleCode 过滤菜单可见性）/
#           dashboard（同 sidebar 过滤动作可见性）；三者运行时都消费 moduleCode。
# router_meta 是纯文档面：authGuard(router/index.js) 只读 roles/permissions，不读 meta.moduleCode →
#           其缺码不构成 fail-open，不纳入 presence 检查（设计决策 2026-06-06，体系设计者确认）。

def test_frontend_routeaccess_missing_modulecode_despite_other_surfaces_fails(truth):  # R2-A1
    # /exams 在 sidebar/router_meta 都有码，但 routeAccess 门控面缺码 → routeAccess 必须独立报红（不被并集掩盖）
    parsed = {"routeAccess": {}, "router_meta": {"/exams": "exam"}, "sidebar": {"/exams": "exam"}, "dashboard": {},
              "_surface_routes": {"routeAccess": {"/exams"}, "router_meta": {"/exams"}, "sidebar": {"/exams"}}}
    errs = cms._compare_frontend(truth, parsed)
    assert any("/exams" in e and "routeAccess" in e and "moduleCode" in e for e in errs), errs


def test_frontend_sidebar_missing_modulecode_despite_routeaccess_fails(truth):  # R2-A2
    # /exams 在 routeAccess 有码，但 sidebar 门控面缺码 → sidebar 必须独立报红
    parsed = {"routeAccess": {"/exams": "exam"}, "router_meta": {}, "sidebar": {}, "dashboard": {},
              "_surface_routes": {"routeAccess": {"/exams"}, "sidebar": {"/exams"}}}
    errs = cms._compare_frontend(truth, parsed)
    assert any("/exams" in e and "sidebar" in e and "moduleCode" in e for e in errs), errs


def test_frontend_dashboard_missing_modulecode_despite_routeaccess_fails(truth):  # R2-A3
    # /homework 在 routeAccess 有码，但 dashboard 门控面缺码 → dashboard 必须独立报红
    parsed = {"routeAccess": {"/homework": "homework"}, "router_meta": {}, "sidebar": {}, "dashboard": {},
              "_surface_routes": {"routeAccess": {"/homework"}, "dashboard": {"/homework"}}}
    errs = cms._compare_frontend(truth, parsed)
    assert any("/homework" in e and "dashboard" in e and "moduleCode" in e for e in errs), errs


def test_frontend_router_meta_missing_modulecode_despite_routeaccess_passes(truth):  # R2-A4：router_meta 文档面豁免锁
    # /exams 在 routeAccess 有码，router_meta 缺码 → router_meta 非门控面，不报红（门控由 routeAccess 承载）。
    # 锁住设计决策：cross-surface 独立 fail-closed 只作用于门控面，router_meta 缺码不算 fail-open。
    parsed = {"routeAccess": {"/exams": "exam"}, "router_meta": {}, "sidebar": {}, "dashboard": {},
              "_surface_routes": {"routeAccess": {"/exams"}, "router_meta": {"/exams"}}}
    errs = cms._compare_frontend(truth, parsed)
    assert not any("/exams" in e and "moduleCode" in e for e in errs), errs


# ===== codex-review F-001 MED 修复：route 字段无序解析 =====
# 旧 _ROUTE_FIELD_MC 仅匹配 route 在前、moduleCode 在后；同对象内字段顺序颠倒（moduleCode 在前 / route 在后）时
# sidebar/dashboard 漏解析 → 受控 route 假阳性「缺失 moduleCode」、null route 带码漏报。_surface_route_set
# 本就只抓 route 字面量（order-insensitive），故两者不对称构成 finding。修复后两方向均须解析为 {route: moduleCode}。

def test_route_field_pairs_modulecode_first(truth):  # F-001 解析层：moduleCode 在前亦须解析（单引号）
    assert cms._parse_route_field_pairs("{ moduleCode: 'exam', route: '/exams' }") == {"/exams": "exam"}


def test_route_field_pairs_route_first_still_parses(truth):  # F-001 解析层：route 在前不回退（双引号）
    assert cms._parse_route_field_pairs('{ route: "/exams", moduleCode: "exam" }') == {"/exams": "exam"}


def test_sidebar_null_route_modulecode_first_reports(truth):  # F-001 A1：sidebar null route moduleCode 在前 → 红
    pairs = cms._parse_route_field_pairs("{ moduleCode: 'exam', route: '/students' }")
    assert pairs == {"/students": "exam"}, pairs
    parsed = {"routeAccess": {}, "router_meta": {}, "sidebar": pairs, "dashboard": {}}
    errs = cms._compare_frontend(truth, parsed)
    assert any("/students" in e and "null" in e for e in errs), errs


def test_dashboard_null_route_modulecode_first_reports(truth):  # F-001 A2：dashboard null route moduleCode 在前 → 红
    pairs = cms._parse_route_field_pairs("{ moduleCode: 'exam', route: '/students' }")
    assert pairs == {"/students": "exam"}, pairs
    parsed = {"routeAccess": {}, "router_meta": {}, "sidebar": {}, "dashboard": pairs}
    errs = cms._compare_frontend(truth, parsed)
    assert any("/students" in e and "null" in e for e in errs), errs


def test_sidebar_route_modulecode_first_no_false_missing(truth):  # F-001 A3：受控 route moduleCode 在前 → 不误报缺失
    pairs = cms._parse_route_field_pairs("{ moduleCode: 'exam', route: '/exams' }")
    assert pairs == {"/exams": "exam"}, pairs
    parsed = {"routeAccess": {}, "router_meta": {}, "sidebar": pairs, "dashboard": {},
              "_surface_routes": {"sidebar": {"/exams"}}}
    errs = cms._compare_frontend(truth, parsed)
    assert not any("/exams" in e and "moduleCode" in e for e in errs), errs


def test_sidebar_route_modulecode_first_mismatch_reports(truth):  # F-001 A4：moduleCode 在前且与真源不一致 → 红
    pairs = cms._parse_route_field_pairs("{ moduleCode: 'conduct', route: '/exams' }")
    assert pairs == {"/exams": "conduct"}, pairs
    parsed = {"routeAccess": {}, "router_meta": {}, "sidebar": pairs, "dashboard": {}}
    errs = cms._compare_frontend(truth, parsed)
    assert any("/exams" in e and "不一致" in e for e in errs), errs


# ===== codex-review F-001 HIGH（R3）：未登记 + 无 moduleCode 的门控面 route fail-closed 缺口 =====
# 根因：cross-surface 检查 want = fr.get(route) 把「真源缺失（未登记）」与「真源显式 null」都坍缩成 None，
# 一并 continue 放行 → 未在 module-semantics.yaml 声明、又无 moduleCode 的新 route 在门控面露出可逃检。
# 修复：门控面分母先按 route∈fr 三态区分：未登记→fail-closed 报红；显式 null→放行；受控缺码→报缺失。

def test_frontend_unregistered_route_no_code_routeaccess_fails(truth):  # 反例 #28（F-001 HIGH R3）
    # /brand-new 未在真源声明 + 无 moduleCode，却在门控面 routeAccess 露出 → 必须 fail-closed（旧逻辑逃检返回 []）
    parsed = {"routeAccess": {}, "router_meta": {}, "sidebar": {}, "dashboard": {},
              "_surface_routes": {"routeAccess": {"/brand-new"}}}
    errs = cms._compare_frontend(truth, parsed)
    assert any("/brand-new" in e for e in errs), errs


def test_frontend_unregistered_route_no_code_sidebar_fails(truth):  # 反例 #29（F-001 HIGH R3）
    parsed = {"routeAccess": {}, "router_meta": {}, "sidebar": {}, "dashboard": {},
              "_surface_routes": {"sidebar": {"/brand-new"}}}
    errs = cms._compare_frontend(truth, parsed)
    assert any("/brand-new" in e for e in errs), errs


def test_frontend_unregistered_route_no_code_dashboard_fails(truth):  # 反例 #30（F-001 HIGH R3）
    parsed = {"routeAccess": {}, "router_meta": {}, "sidebar": {}, "dashboard": {},
              "_surface_routes": {"dashboard": {"/brand-new"}}}
    errs = cms._compare_frontend(truth, parsed)
    assert any("/brand-new" in e for e in errs), errs


def test_frontend_unregistered_route_no_code_router_meta_passes(truth):  # 反例 #31：router_meta 非门控面不报
    # 未登记 route 仅在 router_meta（非门控文档面）露出无码 → 不算 fail-open（设计决策 2026-06-06），不报红
    parsed = {"routeAccess": {}, "router_meta": {}, "sidebar": {}, "dashboard": {},
              "_surface_routes": {"router_meta": {"/brand-new"}}}
    errs = cms._compare_frontend(truth, parsed)
    assert not any("/brand-new" in e for e in errs), errs
