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


CHECKS = [check_self_consistency, check_backend]


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
