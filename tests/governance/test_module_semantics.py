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
# router_meta 自 F-002 路径2（2026-06-06 设计者改判）起亦为门控面：authGuard(router/index.js:180) 消费
#           to.meta.moduleCode → 受控 route 缺码=fail-open。因 surface=全路由表，用专属检查（受控覆盖+动态
#           fail-closed），见 _compare_frontend (3) 段与下方 test_frontend_router_meta_* 用例。

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


def test_frontend_router_meta_controlled_missing_modulecode_fails(truth):  # F-002 路径2：取代旧 R2-A4 文档面豁免锁
    # /exams 受控（fr=exam），即便 routeAccess 有码，router_meta 缺码也报红——router_meta 已升为门控面
    # （authGuard 消费 to.meta），路径2 要求每个受控 route 在 router_meta 标码。旧 R2-A4「router_meta 缺码 passes」
    # 已废止（它正是放过 R4 F-001 profile fail-open 的豁免锁）。
    parsed = {"routeAccess": {"/exams": "exam"}, "router_meta": {}, "sidebar": {}, "dashboard": {},
              "_surface_routes": {"routeAccess": {"/exams"}, "router_meta": {"/exams"}}}
    errs = cms._compare_frontend(truth, parsed)
    assert any("/exams" in e and "router_meta" in e and "moduleCode" in e for e in errs), errs


def test_frontend_router_meta_dynamic_controlled_missing_modulecode_fails(truth):  # F-002 路径2：受控动态 route 缺码（根治 F-001）
    # /profile/student/:studentId 受控（fr=study_analytics），router_meta 露出却无码 → 报。
    # 这正是 R4 F-001 的 fail-open 形态：动态路由 authGuard 唯一靠 to.meta，缺码=直达 fail-open。
    parsed = {"routeAccess": {}, "router_meta": {}, "sidebar": {}, "dashboard": {},
              "_surface_routes": {"router_meta": {"/profile/student/:studentId"}}}
    errs = cms._compare_frontend(truth, parsed)
    assert any("/profile/student/:studentId" in e and "moduleCode" in e for e in errs), errs


def test_frontend_router_meta_dynamic_unregistered_fails(truth):  # F-002 路径2：动态未登记 route fail-closed
    # 新增动态 route /widget/:id 仅在 router_meta 露出、未登记 fr → fail-closed（防新动态受控路由漏登记逃检）。
    parsed = {"routeAccess": {}, "router_meta": {}, "sidebar": {}, "dashboard": {},
              "_surface_routes": {"router_meta": {"/widget/:id"}}}
    errs = cms._compare_frontend(truth, parsed)
    assert any("/widget/:id" in e and "未在 frontend_route_module 声明" in e for e in errs), errs


def test_frontend_router_meta_dynamic_null_route_passes(truth):  # F-002 路径2：动态 null route（如 /joint-exams/:id）放行
    # /joint-exams/:id 真源=null（联考不受模块门控），动态但登记 null → 不 fail-closed、不报缺码。
    parsed = {"routeAccess": {}, "router_meta": {}, "sidebar": {}, "dashboard": {},
              "_surface_routes": {"router_meta": {"/joint-exams/:id"}}}
    errs = cms._compare_frontend(truth, parsed)
    assert not any("/joint-exams/:id" in e for e in errs), errs


def test_frontend_router_meta_catchall_route_passes(truth):  # F-002 路径2：catch-all 404 路由不误报
    # Vue Router catch-all /:pathMatch(.*)* 是框架级 404 redirect，不经模块门控 → (b) 排除，不报。
    parsed = {"routeAccess": {}, "router_meta": {}, "sidebar": {}, "dashboard": {},
              "_surface_routes": {"router_meta": {"/:pathMatch(.*)*"}}}
    errs = cms._compare_frontend(truth, parsed)
    assert not any("pathMatch" in e for e in errs), errs


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


def test_frontend_unregistered_static_route_only_router_meta_passes(truth):  # F-002 路径2：静态未登记仅 router_meta 不 fail-closed
    # 静态未登记 route 仅在 router_meta 露出无码 → 不报。router_meta 门控面只对「动态」route fail-closed
    # （动态 authGuard 唯一靠 to.meta）；静态 route 门控由 routeAccess/sidebar/dashboard 承载，其 fail-closed 兜底。
    # 这类「无 routeAccess 码 + 无 meta 码」的静态 route 在 runtime 本就不门控（等价 null），不报是 fail-open-safe。
    parsed = {"routeAccess": {}, "router_meta": {}, "sidebar": {}, "dashboard": {},
              "_surface_routes": {"router_meta": {"/brand-new"}}}
    errs = cms._compare_frontend(truth, parsed)
    assert not any("/brand-new" in e for e in errs), errs


# ===== Phase 0.6 A — codex-review F-002 MED：frontend known_drift fail-closed =====
# 旧 check_frontend_drift/check_known_drift 都只遍历 truth["known_drift"]，删一行 truth row 就不被遍历 → 逃检，
# known_drift 收敛变账面收敛。修复：以「still_holds 为真的 _FRONTEND_DRIFT_PROBES」为 fail-closed 分母，
# truth 缺失任一仍成立的 drift → 报红。已不成立的 drift 不要求登记（登记着则由下方循环报"疑似已修复"）。

def test_frontend_drift_delete_studio_row_fails(truth):  # 反例 #32（F-002）：删 studio drift row → 逃检必须失败
    bad = copy.deepcopy(truth)
    bad["known_drift"] = [d for d in bad["known_drift"] if d["id"] != "studio-frontend-entry-missing"]
    errs = cms.check_frontend_drift(bad, REPO)
    assert any("studio-frontend-entry-missing" in e and "未在 known_drift 登记" in e for e in errs), errs


def test_frontend_drift_delete_teaching_row_fails(truth):  # 反例 #33（F-002）：删 teaching drift row → 逃检必须失败
    bad = copy.deepcopy(truth)
    bad["known_drift"] = [d for d in bad["known_drift"] if d["id"] != "teaching-frontend-unwired"]
    errs = cms.check_frontend_drift(bad, REPO)
    assert any("teaching-frontend-unwired" in e and "未在 known_drift 登记" in e for e in errs), errs


def test_frontend_drift_complete_registration_passes(truth):  # 正例：真源完整登记 → 不报"未登记"
    errs = cms.check_frontend_drift(truth, REPO)
    assert not any("未在 known_drift 登记" in e for e in errs), errs
