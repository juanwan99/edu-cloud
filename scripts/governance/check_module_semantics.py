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


CHECKS = [check_self_consistency]


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
