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
    # 与 module_middleware.resolve_module_code 严格同算法（0.7B item3 / R5-DC2 + R2 F-001 段边界加固）：
    # exempt-first（基础设施永不门控），再 ROUTE_MODULE_MAP 最长前缀匹配；匹配须在路径段边界
    # （== 或 prefix+'/'），与中间件 _prefix_matches 同义——裸 startswith 会让 /api/v1/conductors 误命中
    # /api/v1/conduct。exempt 与 gated 前缀集互斥，exempt-first 对所有判定 inert，仅锁死两端为同一算法。
    def _seg_match(p: str) -> bool:
        return prefix == p or prefix.startswith(p + "/")
    for p in exempt:
        if _seg_match(p):
            return "exempt"
    for p in sorted(route_map, key=len, reverse=True):
        if _seg_match(p):
            return f"gated:{route_map[p]}"
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


def discover_static_mounts(repo: Path) -> dict[str, dict[str, str]]:
    """Discover non-API StaticFiles mounts that must be in the gate denominator."""
    sys.path.insert(0, str(repo / "src"))
    from starlette.routing import Mount
    from starlette.staticfiles import StaticFiles
    from edu_cloud.api.app import create_app

    app = create_app()
    mounts: dict[str, dict[str, str]] = {}
    for route in app.routes:
        if isinstance(route, Mount) and isinstance(getattr(route, "app", None), StaticFiles):
            mounts[route.path] = {"name": str(getattr(route, "name", "") or "")}
    return mounts


def _compare_static_mounts(truth: dict, discovered: dict[str, dict[str, str]]) -> list[str]:
    errs: list[str] = []
    declared = truth.get("static_mounts", {}) or {}
    for path, actual in discovered.items():
        if path not in declared:
            errs.append(
                f"static mount {path} is not declared in static_mounts "
                f"(actual=static:{actual.get('name')}, fail-closed)"
            )
            continue
        spec = declared[path] or {}
        if spec.get("name") != actual.get("name"):
            errs.append(
                f"static mount {path} name={actual.get('name')} does not match truth {spec.get('name')}"
            )
        if spec.get("expect") != "public_upload_asset":
            errs.append(f"static mount {path} must declare expect=public_upload_asset")
        if spec.get("module_gate") != "exempt":
            errs.append(f"static mount {path} must declare module_gate=exempt")
        if not str(spec.get("reason") or "").strip():
            errs.append(f"static mount {path} must declare a reason")
    for path in declared:
        if path not in discovered:
            errs.append(f"truth static_mounts declares {path} but app has no such mount")
    return errs


def check_static_mounts(truth: dict, repo: Path) -> list[str]:
    return _compare_static_mounts(truth, discover_static_mounts(repo))


# 引号字面量（F-002）：JS 中 route/moduleCode 既可单引号也可双引号，守卫两者都须识别，
# 否则人工/格式化改成双引号后 frontend drift 与野值码会被漏检，流水线误报 clean。
_Q = r"['\"]"          # 单或双引号定界符
_NQ = r"[^'\"]"        # route/path 字面量内容（不含任何引号）


def _strip_js_comments(text: str) -> str:
    text = re.sub(r"//.*", "", text)
    return re.sub(r"/\*.*?\*/", "", text, flags=re.S)


def _parse_route_module_pairs(text: str) -> dict[str, str]:
    """提取形如 '/route': { ... moduleCode: 'x' } 或 path:'/r' ... moduleCode:'x' 的对。
    采用对象级扫描：先按 moduleCode 邻域回溯最近的 route/path 字面量。单/双引号均识别（F-002）。"""
    text = _strip_js_comments(text)
    pairs: dict[str, str] = {}
    # routeAccess: '/route': { permission..., moduleCode: 'x' }
    for m in re.finditer(_Q + r"(/" + _NQ + r"*)" + _Q + r"\s*:\s*\{[^}]*moduleCode:\s*" + _Q + r"([a-z_]+)" + _Q, text):
        pairs[m.group(1)] = m.group(2)
    # router meta: { path: 'r', ... meta: { ... moduleCode: 'x' } }
    for m in re.finditer(r"path:\s*" + _Q + r"(" + _NQ + r"+)" + _Q + r"[^}]*moduleCode:\s*" + _Q + r"([a-z_]+)" + _Q, text):
        route = m.group(1)
        route = route if route.startswith("/") else "/" + route
        pairs.setdefault(route, m.group(2))
    return pairs


def _surface_route_set(text: str, kind: str) -> set[str]:
    """提取某 surface 实际出现的全部 route 字面量（含**不带 moduleCode** 者）——
    F-001 fail-closed 检查的分母。kind ∈ {object_key, path_field, route_field}，单/双引号均识别。"""
    text = _strip_js_comments(text)
    if kind == "object_key":      # routeAccess: '/route': { ... }
        return set(re.findall(_Q + r"(/" + _NQ + r"*)" + _Q + r"\s*:\s*\{", text))
    if kind == "path_field":      # router meta: path: 'r'（归一化前导 /）
        out: set[str] = set()
        for r in re.findall(r"path:\s*" + _Q + r"(" + _NQ + r"+)" + _Q, text):
            out.add(r if r.startswith("/") else "/" + r)
        return out
    # route_field: sidebar / dashboard 的 route: '/route'
    return set(re.findall(r"route:\s*" + _Q + r"(/" + _NQ + r"*)" + _Q, text))


def _parse_route_field_pairs(text: str) -> dict[str, str]:
    """sidebar/dashboard 的 route 字段对：{ route: '/r', ... moduleCode: 'x' }。
    无序解析（codex-review F-001 MED）：同对象内 route 在前或 moduleCode 在前都解析为 {route: moduleCode}；
    _surface_route_set 本就只抓 route 字面量（order-insensitive），此处对齐以消除假阳性/漏报。
    单/双引号均识别（F-002）；`[^}]` 不含右花括号，天然不跨对象边界。"""
    text = _strip_js_comments(text)
    pairs: dict[str, str] = {}
    # route 在前、moduleCode 在后
    for m in re.finditer(r"route:\s*" + _Q + r"(/" + _NQ + r"*)" + _Q + r"[^}]*moduleCode:\s*" + _Q + r"([a-z_]+)" + _Q, text):
        pairs[m.group(1)] = m.group(2)
    # moduleCode 在前、route 在后（顺序颠倒亦须识别）
    for m in re.finditer(r"moduleCode:\s*" + _Q + r"([a-z_]+)" + _Q + r"[^}]*route:\s*" + _Q + r"(/" + _NQ + r"*)" + _Q, text):
        pairs.setdefault(m.group(2), m.group(1))
    return pairs


def parse_frontend(repo: Path) -> dict:
    fe = repo / "frontend/src"
    ra_txt = (fe / "config/routeAccess.js").read_text(encoding="utf-8")
    rm_txt = (fe / "router/index.js").read_text(encoding="utf-8")
    sidebar_txt = _strip_js_comments((fe / "config/sidebarConfig.js").read_text(encoding="utf-8"))
    dash_txt = _strip_js_comments((fe / "pages/DashboardPage.vue").read_text(encoding="utf-8"))
    route_access = _parse_route_module_pairs(ra_txt)
    router_meta = _parse_route_module_pairs(rm_txt)
    sidebar = _parse_route_field_pairs(sidebar_txt)
    # dashboard action 带 route 字段（DashboardPage.vue:435,444,455,465,474），解析 (route, moduleCode) 对，
    # 复用 sidebar 同款无序解析 → 升级为 route 级比对（必修③，不再只野值检查）
    dashboard = _parse_route_field_pairs(dash_txt)
    # _surface_routes：每个 surface 实际露出的全部 route（含无 moduleCode 者），F-001 fail-closed 分母。
    surface_routes = {
        "routeAccess": _surface_route_set(ra_txt, "object_key"),
        "router_meta": _surface_route_set(rm_txt, "path_field"),
        "sidebar": _surface_route_set(sidebar_txt, "route_field"),
        "dashboard": _surface_route_set(dash_txt, "route_field"),
    }
    return {"routeAccess": route_access, "router_meta": router_meta,
            "sidebar": sidebar, "dashboard": dashboard,
            "_surface_routes": surface_routes}


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
    # F-001 fail-closed（codex-review HIGH，R2 收口加强为两层）：受控 route（真源非 null）缺 moduleCode 的两类
    # 缺口都报红。分母 = _surface_routes（含无 moduleCode 的 route）；旧格式 parsed 无此键时退化跳过；
    # null route 缺码正确放行（本就不该 gating）。
    #   门控面 = 运行时真正按 moduleCode 决定可达/可见的面：
    #     routeAccess（canAccessRouteForRole→moduleMatches，路由访问门控）
    #     sidebar（children.filter(c=>!c.moduleCode||enabled.has(c.moduleCode))，菜单可见性）
    #     dashboard（同 sidebar 模式按 moduleCode 过滤动作可见性）
    #   router_meta（authGuard router/index.js:180 消费 `requirement?.moduleCode || to.meta?.moduleCode`）自
    #     2026-06-06（设计者改判，F-002 路径2）起为运行时门控源，不再是纯文档面。但其 surface = 全路由表
    #     （含 /login /parent 等基础设施路由），不能并入 GATING_SURFACES 的整面 fail-closed（否则误伤非门控
    #     路由），改由本函数末尾 (3) 段做「受控覆盖 + 动态 fail-closed」专属校验。
    GATING_SURFACES = ("routeAccess", "sidebar", "dashboard")
    ALL_SURFACES = ("routeAccess", "sidebar", "dashboard", "router_meta")
    surface_routes = parsed.get("_surface_routes")
    if surface_routes:
        # (1) 完全失控兜底：受控 route 露出却在**所有**面均无 moduleCode → 门控彻底丢失（含仅 router_meta 露出
        #     而别处无声明的 orphan 场景，守住上一轮 F-001 HIGH）。
        declared = set()
        for surface in ALL_SURFACES:
            declared |= set(parsed.get(surface, {}).keys())
        for route, want in fr.items():
            if want is None:
                continue
            appears = sorted(s for s in ALL_SURFACES if route in surface_routes.get(s, set()))
            if appears and route not in declared:
                errs.append(f"前端受控 route {route} 在 surface {appears} 露出但所有面均缺失 moduleCode"
                            f"（真源期望 {want}，fail-open 缺口，codex-review F-001）")
        # (2) cross-surface 掩盖（R2）：门控面各自独立 fail-closed —— 受控 route 在某门控面露出却缺码，即使
        #     别的面有码也报红（旧全局并集会被任一面的码掩盖，单门控面删码可逃检）。router_meta 不在此检查内。
        #   F-001 HIGH（codex-review R3）：分母按 route∈fr 三态精确区分——旧 `fr.get(route)` 把「未登记
        #     （route∉fr）」与「真源显式 null」都坍缩成 None 一并放行，致未声明+无 moduleCode 的新 route
        #     在门控面露出可逃检。修复：未登记→fail-closed 报红；显式 null→放行；受控缺码→报缺失 moduleCode。
        for surface in GATING_SURFACES:
            surface_declared = set(parsed.get(surface, {}).keys())
            for route in sorted(surface_routes.get(surface, set())):
                if route in surface_declared:
                    continue  # 带 moduleCode，已由上方逐 surface 循环校验登记/值/null
                if route not in fr:
                    errs.append(f"前端门控面 {surface} 出现未在 frontend_route_module 声明的 route {route}"
                                f"（无 moduleCode，fail-closed 缺口，codex-review F-001 HIGH/R3）")
                elif fr[route] is None:
                    continue  # 真源显式 null（不受门控），缺码正确放行
                else:
                    errs.append(f"前端受控 route {route} 在门控面 {surface} 露出但缺失 moduleCode"
                                f"（真源期望 {fr[route]}，fail-open 缺口，codex-review F-001/R2）")
        # (3) router_meta 门控面（F-002 路径2，2026-06-06 设计者确认）：authGuard 消费 to.meta.moduleCode →
        #     router_meta 已是运行时门控源。因 surface=全路由表，不套用上方整面 fail-closed（避免误伤
        #     /login /parent 等基础设施路由），改两条专属规则：
        #       (a) 受控覆盖：每个受控 route（fr 非 null）若在 router_meta 露出，必须标 moduleCode。
        #       (b) 动态 fail-closed：router_meta 中含动态段(:)的 route 必须在 fr 登记——动态路由 authGuard
        #           唯一靠 to.meta（routeAccess 精确 key 匹配不到模板），漏登记=漏码=fail-open（根治 F-001）。
        rm_surface = surface_routes.get("router_meta", set())
        rm_declared = set(parsed.get("router_meta", {}).keys())
        for route, want in fr.items():  # (a) 受控覆盖
            if want is None:
                continue
            if route in rm_surface and route not in rm_declared:
                errs.append(f"前端受控 route {route} 在门控面 router_meta 露出但缺失 moduleCode"
                            f"（authGuard 消费 to.meta，fail-open 缺口，codex-review F-002 路径2）")
        for route in sorted(rm_surface):  # (b) 动态 fail-closed
            if ":" not in route or "(.*)" in route or route in rm_declared:
                continue  # 非动态 / catch-all(/:pathMatch(.*)* 框架级 404，redirect 不门控) / 已有码 → 跳过
            if route not in fr:
                errs.append(f"前端动态 route {route} 在 router_meta 露出但未在 frontend_route_module 声明"
                            f"（动态路由唯一靠 to.meta，fail-closed，codex-review F-002 路径2）")
            # route in fr 且 fr[route] is None（动态 null route，如 /joint-exams/:id）→ 不受门控，放行
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
    # fail-closed 分母（codex-review F-002）：probe 仍成立(still_holds=True)的 frontend drift 必须在 truth 登记。
    # 旧实现只遍历 truth["known_drift"]，删一行仍成立的 drift row 就不被遍历 → 逃检（账面收敛）。此处以 probe 集为
    # 分母反向校验：仍成立却未登记 → 报红。已不成立的 drift 不要求登记（登记着则由下方循环报"疑似已修复"）。
    registered = {d["id"] for d in truth["known_drift"] if d.get("consumer") == "frontend"}
    for drift_id, probe in _FRONTEND_DRIFT_PROBES.items():
        if probe["still_holds"](parsed) and drift_id not in registered:
            errs.append(f"frontend drift {drift_id} 实际仍成立但未在 known_drift 登记"
                        f"（删登记逃检，fail-closed，codex-review F-002）")
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


CHECKS = [check_self_consistency, check_backend, check_static_mounts, check_frontend, check_frontend_drift, check_portal, check_known_drift]


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
