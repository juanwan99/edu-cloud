"""模块语义一致性守卫（Phase 0.5）。逐入口比对真源，只读，不改业务源码。"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

import yaml

REPO = Path(__file__).resolve().parents[2]
TRUTH_PATH = REPO / "docs/governance/module-semantics.yaml"


def load_truth(path: Path = TRUTH_PATH) -> dict:
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f)


def _module_codes_from_source(repo: Path) -> set[str]:
    src = (repo / "src/edu_cloud/models/school_settings.py").read_text(encoding="utf-8")
    block = re.search(r"MODULE_CODES\s*=\s*\{(.*?)\}", src, re.S).group(1)
    return set(re.findall(r'"([a-z_]+)"\s*:', block))


def _arch_modules_from_modules_yaml(repo: Path) -> set[str]:
    data = yaml.safe_load((repo / "docs/governance/modules.yaml").read_text(encoding="utf-8"))
    return {m["name"] for m in data["modules"]}


def check_self_consistency(truth: dict, repo: Path) -> list[str]:
    errs: list[str] = []
    codes = set(truth["school_module_codes"])
    src_codes = _module_codes_from_source(repo)
    if codes != src_codes:
        errs.append(f"school_module_codes 与 MODULE_CODES 不一致: 真源{codes} vs 源码{src_codes}")
    arch = set(truth["architecture_to_module_code"])
    real_arch = _arch_modules_from_modules_yaml(repo)
    if arch != real_arch:
        errs.append(f"architecture_to_module_code 键集与 modules.yaml 不一致: 缺{real_arch - arch} 多{arch - real_arch}")
    for mod, code in truth["architecture_to_module_code"].items():
        if code is not None and code not in codes:
            errs.append(f"architecture_to_module_code[{mod}]={code} 不是合法开关码")
    return errs


ROUTE_PREFIX_RE = re.compile(r"^(/api/v1/[^/]+)")


def discover_backend_prefixes(repo: Path) -> set[str]:
    """FastAPI app.routes 展开取真实 endpoint，归约到 /api/v1/<seg> 前缀集。
    自动覆盖 prefix='/api/v1/<m>' 与 prefix='/api/v1'+decorator 两形态。"""
    sys.path.insert(0, str(repo / "src"))
    from edu_cloud.api.app import create_app

    app = create_app()
    prefixes: set[str] = set()
    for route in app.routes:
        path = getattr(route, "path", "")
        m = ROUTE_PREFIX_RE.match(path)
        if m:
            prefixes.add(m.group(1))
    return prefixes


def _actual_gating(prefix: str, repo: Path) -> str:
    """读 module_middleware.py 的 ROUTE_MODULE_MAP/EXEMPT，判定 prefix 实际状态。"""
    src = (repo / "src/edu_cloud/api/module_middleware.py").read_text(encoding="utf-8")
    mp = re.search(r"ROUTE_MODULE_MAP\s*=\s*\{(.*?)\}", src, re.S).group(1)
    route_map = dict(re.findall(r'"(/api/v1/[^"]+)"\s*:\s*"([a-z_]+)"', mp))
    ex = re.search(r"EXEMPT_PREFIXES\s*=\s*\((.*?)\)", src, re.S).group(1)
    exempt = re.findall(r'"(/[^"]+)"', ex)
    # middleware 用 startswith：最长匹配优先以稳定判定
    for p in sorted(route_map, key=len, reverse=True):
        if prefix.startswith(p):
            return f"gated:{route_map[p]}"
    for p in exempt:
        if prefix.startswith(p):
            return "exempt"
    return "pass-through"


def _compare_backend(truth: dict, discovered_actual: dict[str, str]) -> list[str]:
    """discovered_actual: {prefix: actual_state}。与真源 backend_routes 比对。"""
    errs: list[str] = []
    routes = truth["backend_routes"]
    drift_by_id = {d["id"]: d for d in truth["known_drift"]}
    for prefix, actual in discovered_actual.items():
        if prefix not in routes:
            errs.append(f"后端入口 {prefix} 未在真源 backend_routes 声明（actual={actual}，fail-closed）")
            continue
        spec = routes[prefix]
        expect = spec["expect"]
        if actual == expect:
            # 已达期望但仍挂 drift 登记 → stale drift（设计契约：入口被修复后强制删除登记，plan-review R4 F-001）
            stale_drift = spec.get("drift")
            if stale_drift:
                errs.append(f"后端 {prefix} 实际已达期望 {expect}，但仍登记 drift={stale_drift}（疑似已修复，应从 backend_routes drift 字段 + known_drift 删除）")
            continue
        drift_id = spec.get("drift")
        if not drift_id:
            errs.append(f"后端 {prefix} 期望 {expect} 实际 {actual}，无 drift 登记")
            continue
        d = drift_by_id.get(drift_id)
        # 四元组匹配（GPT P1-b）：actual 必须与登记一致，否则元组漂移
        if d is None:
            errs.append(f"后端 {prefix} 引用的 drift={drift_id} 不在 known_drift")
        elif not (d["consumer"] == "backend_middleware" and d["locus"] == prefix
                  and d["expect"] == expect and d["actual"] == actual):
            errs.append(f"drift {drift_id} 四元组与实际不符: 登记 actual={d.get('actual')} vs 实际 {actual}")
    # 反向覆盖（plan-review F2）：真源声明的 prefix 必须被 discovery 发现，否则是 stale 条目
    for prefix in routes:
        if prefix not in discovered_actual:
            errs.append(f"真源 backend_routes 声明的 {prefix} 未被 route discovery 发现（stale 条目，应删除）")
    return errs


def check_backend(truth: dict, repo: Path) -> list[str]:
    prefixes = discover_backend_prefixes(repo)
    discovered = {p: _actual_gating(p, repo) for p in prefixes}
    return _compare_backend(truth, discovered)


def _strip_js_comments(text: str) -> str:
    text = re.sub(r"//.*", "", text)
    return re.sub(r"/\*.*?\*/", "", text, flags=re.S)


def _parse_route_module_pairs(text: str) -> dict[str, str]:
    """提取形如 '/route': { ... moduleCode: 'x' } 或 path:'/r' ... moduleCode:'x' 的对。
    采用对象级扫描：先按 moduleCode 邻域回溯最近的 route/path 字面量。"""
    text = _strip_js_comments(text)
    pairs: dict[str, str] = {}
    # routeAccess: '/route': { permission..., moduleCode: 'x' }
    for m in re.finditer(r"'(/[^']*)'\s*:\s*\{[^}]*moduleCode:\s*'([a-z_]+)'", text):
        pairs[m.group(1)] = m.group(2)
    # router meta: { path: 'r', ... meta: { ... moduleCode: 'x' } }
    for m in re.finditer(r"path:\s*'([^']+)'[^}]*moduleCode:\s*'([a-z_]+)'", text):
        route = m.group(1)
        route = route if route.startswith("/") else "/" + route
        pairs.setdefault(route, m.group(2))
    return pairs


def parse_frontend(repo: Path) -> dict:
    fe = repo / "frontend/src"
    route_access = _parse_route_module_pairs((fe / "config/routeAccess.js").read_text(encoding="utf-8"))
    router_meta = _parse_route_module_pairs((fe / "router/index.js").read_text(encoding="utf-8"))
    sidebar_txt = _strip_js_comments((fe / "config/sidebarConfig.js").read_text(encoding="utf-8"))
    sidebar = dict(re.findall(r"route:\s*'(/[^']*)'[^}]*moduleCode:\s*'([a-z_]+)'", sidebar_txt))
    dash_txt = _strip_js_comments((fe / "pages/DashboardPage.vue").read_text(encoding="utf-8"))
    # dashboard action 带 route 字段（DashboardPage.vue:435,444,455,465,474），解析 (route, moduleCode) 对，
    # 复用 sidebar 同款正则 → 升级为 route 级比对（必修③，不再只野值检查）
    dashboard = dict(re.findall(r"route:\s*'(/[^']*)'[^}]*moduleCode:\s*'([a-z_]+)'", dash_txt))
    return {"routeAccess": route_access, "router_meta": router_meta,
            "sidebar": sidebar, "dashboard": dashboard}


def _compare_frontend(truth: dict, parsed: dict) -> list[str]:
    errs: list[str] = []
    codes = set(truth["school_module_codes"])
    fr = truth["frontend_route_module"]
    # routeAccess / sidebar / dashboard / router_meta：均纳入 fail-closed + 一致性 + null 检查
    #   F-001(R5)：router_meta 动态路由(/exams/:id 等)纳入同一基线分母，改 fail-closed（不再"不强制声明"）
    #   F-002(R5)：null route（真源声明不受门控）出现 moduleCode → 红
    # 注：parse_frontend 仅捕获带 moduleCode 的条目，故 fr 须覆盖四面全部「带 moduleCode」的 route（含 6 动态路由）。
    for surface in ("routeAccess", "sidebar", "dashboard", "router_meta"):
        for route, code in parsed[surface].items():
            if route not in fr:
                errs.append(f"前端 {surface} 出现未在 frontend_route_module 声明的 route {route}（fail-closed，plan-review F1/R5 F-001）")
            elif fr[route] is None:
                errs.append(f"前端 {surface} {route} 真源期望 null（不受模块门控）却出现 moduleCode={code}（R5 F-002：null route 不应 gating）")
            elif code != fr[route]:
                errs.append(f"前端 {surface} {route} moduleCode={code} 与真源 {fr[route]} 不一致")
    # routeAccess 与 router-meta 同 route 一致性（双源交叉校验）
    for route in set(parsed["routeAccess"]) & set(parsed["router_meta"]):
        if parsed["routeAccess"][route] != parsed["router_meta"][route]:
            errs.append(f"前端 {route} 在 routeAccess 与 router-meta 间不一致")
    # 野值检查（兜底）：所有面出现的 code ∈ 9
    for code in (list(parsed["sidebar"].values()) + list(parsed["dashboard"].values())
                 + list(parsed["routeAccess"].values()) + list(parsed["router_meta"].values())):
        if code not in codes:
            errs.append(f"前端出现野值 moduleCode={code}（∉ 9 开关码）")
    return errs


def check_frontend(truth: dict, repo: Path) -> list[str]:
    return _compare_frontend(truth, parse_frontend(repo))


def _load_service_catalog(repo: Path) -> list[dict]:
    sys.path.insert(0, str(repo / "src"))
    from edu_cloud.modules.portal.service import SERVICE_CATALOG
    return [dict(item) for item in SERVICE_CATALOG]


def _compare_portal(truth: dict, catalog: list[dict]) -> list[str]:
    errs: list[str] = []
    codes = set(truth["school_module_codes"])
    for item in catalog:
        mc = item.get("module_code")
        if mc not in codes:
            errs.append(f"Portal service {item.get('id')} module_code={mc} ∉ 9 开关码")
        elif truth.get("portal_services_expect_self_module") and item.get("id") != mc:
            errs.append(f"Portal service id={item.get('id')} != module_code={mc}")
    return errs


def check_portal(truth: dict, repo: Path) -> list[str]:
    return _compare_portal(truth, _load_service_catalog(repo))


# frontend drift 实际探测器（plan-review F2）：id -> fn(parsed) -> bool（drift 是否「仍成立」）
# 不硬编码白名单放行；每个 frontend drift 必须有探测器实际验证，新增无探测器 → fail-closed。
def _all_frontend_codes(parsed: dict) -> set[str]:
    return (set(parsed["routeAccess"].values()) | set(parsed["router_meta"].values())
            | set(parsed["sidebar"].values()) | set(parsed["dashboard"].values()))


def _academic_wired_to_teaching(parsed: dict) -> bool:
    for surface in ("routeAccess", "router_meta"):
        for route, code in parsed[surface].items():
            if route.startswith("/academic") and code == "teaching":
                return True
    return False


# frontend drift 探测器（plan-review F2 + R5 F-003）：id -> {expect, actual, still_holds(parsed)->bool}
# 四元组校验：known_drift 条目的 expect/actual 必须与 probe 契约一致（consumer=frontend 固定、locus 在条目），
# 再由 still_holds 验证实际状态。消除"声称四元组豁免但实仅 probe"的不自洽（R5 F-003）。
_FRONTEND_DRIFT_PROBES = {
    "studio-frontend-entry-missing": {
        "locus": "studio-entry", "expect": "present", "actual": "absent",
        "still_holds": lambda p: "studio" not in _all_frontend_codes(p)},
    "teaching-frontend-unwired": {
        "locus": "/academic/*", "expect": "moduleCode:teaching", "actual": "null",
        "still_holds": lambda p: not _academic_wired_to_teaching(p)},
}


def check_frontend_drift(truth: dict, repo: Path) -> list[str]:
    """frontend drift 四元组校验（R5 F-003）+ 实际状态校验：
    登记 expect/actual 须与 probe 契约一致；drift 仍成立→绿；实际已不成立(疑似已修复)→红(应删登记)。"""
    errs: list[str] = []
    parsed = parse_frontend(repo)
    for d in truth["known_drift"]:
        if d["consumer"] != "frontend":
            continue
        probe = _FRONTEND_DRIFT_PROBES.get(d["id"])
        if probe is None:
            continue  # 无探测器的 frontend drift 由 check_known_drift 报 fail-closed
        # 四元组：登记的 locus/expect/actual 必须与 probe 契约匹配（R5 F-003 + Task 5.1 locus）
        if (d.get("locus") != probe["locus"] or d.get("expect") != probe["expect"]
                or d.get("actual") != probe["actual"]):
            errs.append(f"frontend drift {d['id']} 登记 locus/expect/actual=({d.get('locus')},{d.get('expect')},{d.get('actual')}) 与 probe 契约 ({probe['locus']},{probe['expect']},{probe['actual']}) 不符（R5 F-003）")
        if not probe["still_holds"](parsed):
            errs.append(f"frontend drift {d['id']} 实际已不成立（疑似已修复）→ 应从 known_drift 删除")
    return errs


def check_known_drift(truth: dict, repo: Path) -> list[str]:
    """收敛：backend drift 必须被某 backend_route 的 drift 字段引用；
    frontend drift 必须有实际探测器（由 check_frontend_drift 验证状态）。无硬编码白名单放行。"""
    errs: list[str] = []
    backend_refs = {s.get("drift") for s in truth["backend_routes"].values() if s.get("drift")}
    for d in truth["known_drift"]:
        consumer = d["consumer"]
        if consumer == "backend_middleware":
            if d["id"] not in backend_refs:
                errs.append(f"孤儿 backend known_drift: {d['id']} 未被任何 backend_route 引用")
        elif consumer == "frontend":
            if d["id"] not in _FRONTEND_DRIFT_PROBES:
                errs.append(f"frontend known_drift {d['id']} 无实际探测器，无法验证状态（fail-closed）")
        else:
            errs.append(f"known_drift {d['id']} consumer={consumer} 为未知类型")
    return errs


CHECKS = [check_self_consistency, check_backend, check_frontend, check_frontend_drift, check_portal, check_known_drift]


def run_all(truth: dict, repo: Path) -> list[str]:
    errs: list[str] = []
    for check in CHECKS:
        errs += check(truth, repo)
    return errs


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    parser.parse_args()
    truth = load_truth()
    errs = run_all(truth, REPO)
    if errs:
        for e in errs:
            print(f"[module-semantics] FAIL: {e}", file=sys.stderr)
        return 1
    print("Module semantics baseline clean")
    return 0


if __name__ == "__main__":
    sys.exit(main())
