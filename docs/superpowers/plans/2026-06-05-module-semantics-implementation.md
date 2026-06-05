---
phase: impl
---

# Phase 0.5 模块语义统一 实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 建立架构模块↔学校开关码的逐入口声明式真源 + 逐路由比对的只读守卫，把多方消费者现状冻结成基线、按四元组精确豁免已知漂移、禁止新增 fail-open，全程不改业务行为。

**Architecture:** 真源 `module-semantics.yaml`（4 层）作单一声明源；守卫 `check_module_semantics.py` 通过 **FastAPI `app.routes` 展开**取后端真实 endpoint 全集（自动覆盖 `prefix="/api/v1/<m>"` 与 `prefix="/api/v1"`+decorator 两形态），通过正则解析前端 4 方 + Portal `SERVICE_CATALOG`，逐入口与真源比对，drift 按 `(consumer,locus,expect,actual)` 四元组放行；CI 接入。

**Tech Stack:** Python 3.14 / PyYAML / FastAPI（route 展开）/ pytest / 正则解析前端 JS。

> **设计真源：** `docs/superpowers/specs/2026-06-05-module-semantics-design.md`（v4）。本计划实现其 §3 真源 + §4 守卫六项 check + §5 反例矩阵（21 编号 / 23 反例测试）。
> **Commit 边界：** spec §6 的"真源 / 守卫+测试+CI"两逻辑批次，按 TDD 细分为 6 个小 commit（每 commit ≤ 2 文件、< 500 行，满足 `derivation_scale_guard`）。

---

## File Structure

- **Create** `docs/governance/module-semantics.yaml` — 真源（4 层：开关码镜像 / 架构模块归属 / 逐入口期望表 / known_drift）。纯数据。
- **Create** `scripts/governance/check_module_semantics.py` — 守卫。函数边界：`load_truth()` / `check_self_consistency()` / `check_backend()` / `check_frontend()` / `check_frontend_drift()` / `check_portal()` / `check_known_drift()` / `main()`。**6 个 check 函数**（`CHECKS` 列表，与 spec §4 六项一一对应）；各 check 返回 `list[str]`（错误消息），`main` 聚合 + exit code。
- **Create** `tests/governance/test_module_semantics.py` — 正例 4（self/backend/frontend/portal 各 `*_passes_on_real`）+ 反例 23（21 编号，#7 与 #13 各拆 2）= 端到端 27 测试。
- **Modify** `.github/workflows/test.yml` — **backend job**（重依赖，已 `pip install -e ".[dev]"`）末尾加 `test_module_semantics` + `--check` 两行；governance job 轻依赖（仅 pytest+pyyaml）跑不了 `import create_app`，故不接 governance job（必修②）。

---

## Task 1: 声明真源 yaml（Commit 1）

**Files:**
- Create: `docs/governance/module-semantics.yaml`

- [ ] **Step 1: 写真源文件**

完整写入（内容取自 spec §3 v4，已含 grades/teachers 与 11 条 known_drift；**不含 `/api/v1/subjects`**——非顶层 segment，见 spec §1.1）：

```yaml
version: 2

# ── 第一层：9 个学校开关码（镜像 school_settings.py::MODULE_CODES）
school_module_codes: [exam, grading, homework, study_analytics, research, teaching, calendar, studio, conduct]

# ── 第二层：23 架构模块 → 开关码归属（键集校验自 modules.yaml）
architecture_to_module_code:
  exam: exam
  exam_import: exam
  scan: exam
  card: exam
  pipeline: exam
  paper: exam
  grading: grading
  marking: grading
  analytics: study_analytics
  profile: study_analytics
  adaptive: study_analytics
  knowledge: research
  knowledge_tree: research
  bank: research
  homework: homework
  calendar: calendar
  studio: studio
  conduct: conduct
  academic: teaching
  menu: null
  portal: null
  school: null
  student: null

# ── 第三层：逐入口期望表
backend_routes:
  /api/v1/exams:            { expect: "gated:exam" }
  /api/v1/questions:        { expect: "gated:exam" }
  /api/v1/scan:             { expect: "gated:exam" }
  /api/v1/card:             { expect: "gated:exam" }
  /api/v1/templates:        { expect: "gated:exam" }
  /api/v1/pipeline:         { expect: "gated:exam" }
  /api/v1/grading:          { expect: "gated:grading" }
  /api/v1/marking:          { expect: "gated:grading" }
  /api/v1/analytics:        { expect: "gated:study_analytics" }
  /api/v1/knowledge:        { expect: "gated:research" }
  /api/v1/knowledge-tree:   { expect: "gated:research" }
  /api/v1/bank:             { expect: "gated:research" }
  /api/v1/calendar:         { expect: "gated:calendar" }
  /api/v1/studio:           { expect: "gated:studio" }
  /api/v1/homework:         { expect: "gated:homework" }
  /api/v1/academic:         { expect: "gated:teaching", drift: academic-backend-fail-open }
  /api/v1/conduct:          { expect: "gated:conduct",  drift: conduct-backend-fail-open }
  /api/v1/exam-imports:     { expect: "gated:exam",     drift: exam-import-backend-fail-open }
  /api/v1/profile:          { expect: "gated:study_analytics", drift: profile-backend-fail-open }
  /api/v1/menus:            { expect: "exempt", drift: menus-not-in-exempt-list }
  /api/v1/portal:           { expect: "exempt", drift: portal-not-in-exempt-list }
  /api/v1/grades:           { expect: "exempt", drift: grades-not-in-exempt-list }
  /api/v1/teachers:         { expect: "exempt", drift: teachers-not-in-exempt-list }
  /api/v1/client-logs:      { expect: "exempt", drift: client-logs-not-in-exempt-list }
  /api/v1/auth:             { expect: "exempt" }
  /api/v1/health:           { expect: "exempt" }
  /api/v1/version:          { expect: "exempt" }
  /api/v1/schools:          { expect: "exempt" }
  /api/v1/dashboard:        { expect: "exempt" }
  /api/v1/ai:               { expect: "exempt" }
  /api/v1/classes:          { expect: "exempt" }
  /api/v1/students:         { expect: "exempt" }
  /api/v1/joint-exams:      { expect: "exempt" }
  /api/v1/notifications:    { expect: "exempt" }
  /api/v1/llm-config:       { expect: "exempt" }
  /api/v1/workspace:        { expect: "exempt" }

frontend_route_module:
  /exams: exam
  /exam-import: exam
  /marking: grading
  /grading/tasks: grading
  /ai-grading: grading
  /analytics/report: study_analytics
  /analytics/ai-report: study_analytics
  /homework: homework
  /question-bank: research
  /knowledge-tree: research
  /error-book: research
  /conduct: conduct
  /conduct/settings: conduct
  /calendar: calendar
  # 动态/detail 路由（router-meta 专有，R5 F-001 纳入同一基线分母）
  /exams/:id: exam
  /card-dev/:examId: exam
  /grading/tasks/:id: grading
  /marking/grade/:questionId: grading
  /exams/:examId/ai-grading/:subjectId: grading
  /analytics/:examId: study_analytics
  /students: null
  /joint-exams: null
  /school-settings: null
  /academic/teaching-plans: null
  /academic/timetable: null
  /academic/semesters: null
  /assignments: null
  /selections: null
  /teachers: null
  /schools: null
  /admin/impersonate: null

portal_services_expect_self_module: true
dashboard_actions_expect_valid_only: true

# ── 第四层：已知漂移登记（11 条 = 9 backend + 2 frontend；守卫按 consumer+locus+expect+actual 四元组匹配）
known_drift:
  - { id: academic-backend-fail-open,    consumer: backend_middleware, locus: /api/v1/academic,     expect: "gated:teaching",         actual: "pass-through", severity: security }
  - { id: conduct-backend-fail-open,     consumer: backend_middleware, locus: /api/v1/conduct,      expect: "gated:conduct",          actual: "pass-through", severity: security }
  - { id: exam-import-backend-fail-open, consumer: backend_middleware, locus: /api/v1/exam-imports, expect: "gated:exam",             actual: "pass-through", severity: security }
  - { id: profile-backend-fail-open,     consumer: backend_middleware, locus: /api/v1/profile,      expect: "gated:study_analytics",  actual: "pass-through", severity: security }
  - { id: menus-not-in-exempt-list,      consumer: backend_middleware, locus: /api/v1/menus,        expect: "exempt",                 actual: "pass-through", severity: hygiene }
  - { id: portal-not-in-exempt-list,     consumer: backend_middleware, locus: /api/v1/portal,       expect: "exempt",                 actual: "pass-through", severity: hygiene }
  - { id: grades-not-in-exempt-list,     consumer: backend_middleware, locus: /api/v1/grades,       expect: "exempt",                 actual: "pass-through", severity: hygiene }
  - { id: teachers-not-in-exempt-list,   consumer: backend_middleware, locus: /api/v1/teachers,     expect: "exempt",                 actual: "pass-through", severity: hygiene }
  - { id: client-logs-not-in-exempt-list, consumer: backend_middleware, locus: /api/v1/client-logs, expect: "exempt",                 actual: "pass-through", severity: hygiene }
  - { id: studio-frontend-entry-missing, consumer: frontend,           locus: "studio-entry",       expect: "present",                actual: "absent",       severity: ux }
  - { id: teaching-frontend-unwired,     consumer: frontend,           locus: "/academic/*",        expect: "moduleCode:teaching",    actual: "null",         severity: semantic }
```

- [ ] **Step 2: 验证可解析**

Run: `.venv/bin/python -c "import yaml; d=yaml.safe_load(open('docs/governance/module-semantics.yaml')); print(len(d['backend_routes']), len(d['known_drift']), len(d['architecture_to_module_code']))"`
Expected: `36 11 23`（backend_routes 36 == `app.routes` 实测顶层 segment 数；known_drift 11；架构模块 23）

- [ ] **Step 3: Commit**

```bash
git add docs/governance/module-semantics.yaml
```
Then (单独执行纯 git commit，本仓 commit-guard 禁止 stage+commit 复合):
```bash
git commit -m "governance: 增加模块语义映射真源 module-semantics.yaml"
```

---

## Task 2: 守卫骨架 + 真源自洽校验（§4.1）

**Files:**
- Create: `scripts/governance/check_module_semantics.py`
- Test: `tests/governance/test_module_semantics.py`

- [ ] **Step 1: 写失败测试（self-consistency 反例 #8 #9 + 正例）**

```python
# tests/governance/test_module_semantics.py
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
```

- [ ] **Step 2: 跑测试确认失败**

Run: `.venv/bin/python -m pytest tests/governance/test_module_semantics.py -q`
Expected: FAIL（`ModuleNotFoundError: scripts.governance.check_module_semantics`）

- [ ] **Step 3: 写守卫骨架 + load_truth + check_self_consistency**

```python
# scripts/governance/check_module_semantics.py
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
```

- [ ] **Step 4: 跑测试确认通过**

Run: `.venv/bin/python -m pytest tests/governance/test_module_semantics.py -q`
Expected: PASS (3 passed)

- [ ] **Step 5: Commit**

```bash
git add scripts/governance/check_module_semantics.py tests/governance/test_module_semantics.py
```
```bash
git commit -m "governance: 模块语义守卫骨架 + 真源自洽校验"
```

---

## Task 3: 后端逐入口比对（§4.2，route 展开 + 四元组 drift）

**Files:**
- Modify: `scripts/governance/check_module_semantics.py`
- Modify: `tests/governance/test_module_semantics.py`

- [ ] **Step 1: 写失败测试（反例 #1 #2 #3 #11 #12 + 后端正例）**

```python
# 追加到 tests/governance/test_module_semantics.py

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
```

- [ ] **Step 2: 跑测试确认失败**

Run: `.venv/bin/python -m pytest tests/governance/test_module_semantics.py -q`
Expected: FAIL（`AttributeError: check_backend / _compare_backend / discover_backend_prefixes`）

- [ ] **Step 3: 实现后端比对（route 展开 + gating 判定 + 四元组 drift）**

```python
# 追加到 check_module_semantics.py（在 CHECKS 定义前）

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
```

注意 `_actual_gating` 把真源 `expect: "pass-through"` 形态对齐到 known_drift 的 `actual: "pass-through"`；fail-open/exempt drift 的 `actual` 均登记为 `pass-through`，与 `_actual_gating` 返回值一致。

将 `check_backend` 加入 CHECKS：

```python
CHECKS = [check_self_consistency, check_backend]
```

- [ ] **Step 4: 跑测试确认通过**

Run: `.venv/bin/python -m pytest tests/governance/test_module_semantics.py -q`
Expected: PASS (11 passed)

- [ ] **Step 5: Commit**

```bash
git add scripts/governance/check_module_semantics.py tests/governance/test_module_semantics.py
```
```bash
git commit -m "governance: 模块语义守卫 - 后端逐入口比对(route展开+四元组drift)"
```

---

## Task 4: 前端逐 route 比对（§4.3）

**Files:**
- Modify: `scripts/governance/check_module_semantics.py`
- Modify: `tests/governance/test_module_semantics.py`

- [ ] **Step 1: 写失败测试（反例 #4 #5 #6 + 前端正例）**

```python
# 追加到 test_module_semantics.py

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
```

- [ ] **Step 2: 跑测试确认失败**

Run: `.venv/bin/python -m pytest tests/governance/test_module_semantics.py -q`
Expected: FAIL（`AttributeError: check_frontend / _compare_frontend`）

- [ ] **Step 3: 实现前端解析 + 比对**

```python
# 追加到 check_module_semantics.py

FE = REPO / "frontend/src"


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
```

加入 CHECKS：

```python
CHECKS = [check_self_consistency, check_backend, check_frontend]
```

- [ ] **Step 4: 跑测试确认通过**

Run: `.venv/bin/python -m pytest tests/governance/test_module_semantics.py -q`
Expected: PASS (20 passed)。若前端正例失败，按 stderr 提示的真实漂移核对真源 `frontend_route_module`（应与现状一致；现状漂移须在 known_drift，不在 frontend 比对里报红——见 Task 5 对 frontend drift 的豁免）。注：dashboard 现纳入 fail-closed + 一致性，其 5 个 route（/grading/tasks /marking /analytics/report /analytics/ai-report /homework）均已在 `frontend_route_module` 且一致，正例绿（必修③）。

- [ ] **Step 5: Commit**

```bash
git add scripts/governance/check_module_semantics.py tests/governance/test_module_semantics.py
```
```bash
git commit -m "governance: 模块语义守卫 - 前端4方逐route比对"
```

---

## Task 5: Portal 比对 + known_drift 收敛（§4.4 §4.5）

**Files:**
- Modify: `scripts/governance/check_module_semantics.py`
- Modify: `tests/governance/test_module_semantics.py`

- [ ] **Step 1: 写失败测试（反例 #7 #10 + portal/收敛正例）**

```python
# 追加到 test_module_semantics.py

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
```

- [ ] **Step 2: 跑测试确认失败**

Run: `.venv/bin/python -m pytest tests/governance/test_module_semantics.py -q`
Expected: FAIL（`AttributeError: check_portal / _compare_portal / check_known_drift`）

- [ ] **Step 3: 实现 portal 比对 + known_drift 收敛**

```python
# 追加到 check_module_semantics.py

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
        "expect": "present", "actual": "absent",
        "still_holds": lambda p: "studio" not in _all_frontend_codes(p)},
    "teaching-frontend-unwired": {
        "expect": "moduleCode:teaching", "actual": "null",
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
        # 四元组：登记的 expect/actual 必须与 probe 契约匹配（R5 F-003）
        if d.get("expect") != probe["expect"] or d.get("actual") != probe["actual"]:
            errs.append(f"frontend drift {d['id']} 登记 expect/actual=({d.get('expect')},{d.get('actual')}) 与 probe 契约 ({probe['expect']},{probe['actual']}) 不符（R5 F-003）")
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
```

加入 CHECKS（最终顺序）：

```python
CHECKS = [check_self_consistency, check_backend, check_frontend, check_frontend_drift, check_portal, check_known_drift]
```

- [ ] **Step 4: 跑测试确认通过**

Run: `.venv/bin/python -m pytest tests/governance/test_module_semantics.py -q`
Expected: PASS (27 passed)

- [ ] **Step 5: Commit**

```bash
git add scripts/governance/check_module_semantics.py tests/governance/test_module_semantics.py
```
```bash
git commit -m "governance: 模块语义守卫 - Portal比对+known_drift收敛"
```

---

## Task 6: 正例全绿验收 + CI 接入

**Files:**
- Modify: `.github/workflows/test.yml`
- Test: 端到端 `--check`

- [ ] **Step 1: 端到端 --check 在当前代码绿 + 行为不变验证**

Run: `.venv/bin/python scripts/governance/check_module_semantics.py --check; echo "exit=$?"`
Expected: `Module semantics baseline clean` + `exit=0`

Run（行为不变验证，消费者源码零改）: `git diff --stat HEAD -- src/edu_cloud/api/module_middleware.py frontend/src/config/routeAccess.js frontend/src/config/sidebarConfig.js frontend/src/router/index.js frontend/src/pages/DashboardPage.vue src/edu_cloud/modules/portal/service.py frontend/src/api/schoolSettings.js`
Expected: 空输出（这些文件零改动）

- [ ] **Step 2: 全量 governance 测试不回归**

Run: `.venv/bin/python -m pytest tests/governance -q`
Expected: PASS（含既有 + 22 新增，无 fail）

- [ ] **Step 3: CI 接入（backend job，必修②）**

`check_module_semantics.py` 的 `discover_backend_prefixes` 需 `from edu_cloud.api.app import create_app`、`_load_service_catalog` 需 import `SERVICE_CATALOG` → **重依赖（fastapi 全套）**。CI 中 `governance` job 仅 `python -m pip install pytest pyyaml`（轻依赖，无 fastapi），import 会失败；`backend` job 已 `pip install -e ".[dev]" pymupdf`（重依赖）。故接入点选 **backend job**，命令用 `python`（CI runner，**非**本地 `.venv/bin/python`）。

`backend` job 的 pytest 带 `--ignore=tests/governance`，不会自动跑本测试 → 在 backend job 末尾（`- run: python -m pytest tests/test_alembic_migration.py -q` 那行之后）追加两行（缩进对齐既有 `- run:`，6 空格）：

```yaml
      - run: python -m pytest tests/governance/test_module_semantics.py -q
      - run: python scripts/governance/check_module_semantics.py --check
```

> **不接 governance job**：该 job 设计为轻依赖纯静态检查，引入 fastapi 会破坏其边界。保留 `app.routes` 实测（Must Preserve）优先于"为挪进轻 job 而降级为 AST"。本地验收仍用 `.venv/bin/python`（Step 1）。

- [ ] **Step 4: 提交（CI 一行 + 验收说明）**

```bash
git add .github/workflows/test.yml
```
```bash
git commit -m "ci: 模块语义守卫纳入测试流水线"
```

---

## Self-Review（计划自检）

**1. Spec 覆盖：** §3 真源 4 层 → Task 1；§4 第1类自洽 → Task 2；第2类后端逐入口 → Task 3；第3类前端逐 route（含 dashboard route 级比对，必修③）→ Task 4；第4类 frontend drift 探测 + 第5类 Portal + 第6类 known_drift 收敛 → Task 5；§5 反例（23 测试 / 21 编号）→ #8#9(T2) #1#2#3#11#12#14#18(T3) #4#5#6#15#16#17#19#21(T4) #7×2#10#13a#13b#20(T5)；§7 验收（绿 + 零 diff）→ Task 6。覆盖完整。

**2. Placeholder 扫描：** 无 TBD / 无"add error handling"；每 step 含完整代码或精确命令 + expected。

**3. 类型/签名一致：** `load_truth`/`check_self_consistency`/`check_backend`/`_compare_backend`/`discover_backend_prefixes`/`_actual_gating`/`check_frontend`/`_compare_frontend`/`parse_frontend`/`check_frontend_drift`/`_FRONTEND_DRIFT_PROBES`/`_all_frontend_codes`/`check_portal`/`_compare_portal`/`_load_service_catalog`/`check_known_drift` 在定义任务与测试调用处签名一致；`CHECKS` 列表逐 task 追加，最终 **6 个 check**（`check_self_consistency` / `check_backend` / `check_frontend` / `check_frontend_drift` / `check_portal` / `check_known_drift`）。`parse_frontend` 的 dashboard 返回 dict（必修③），`_all_frontend_codes` 取 `.values()`。

**4. 已知风险与契约（plan-review R1 处置后）：**
- 反例 #5 已改为硬断言（要求消息同时含 `/exams`+`routeAccess`+`router-meta`），实现时 `_compare_frontend` 冲突消息须为 `前端 {route} 在 routeAccess 与 router-meta 间不一致`，使断言稳定命中。
- 前端正则解析若现状有未覆盖写法（多行对象），按 `check_permission_mirror.py` 的 `_extract_balanced` 手法增强，不放宽校验。
- **risk_modules / test_debt**（对应 spec §4.1，F4；plan-review R2 F3 补全 + 必修⑥）：高风险消费者 = `module_middleware`(后端门禁) / `routeAccess`+`router-meta`(前端可见性) / `sidebarConfig.js`(侧边栏) / `DashboardPage.vue`(首页硬编码，route 级比对) / `SERVICE_CATALOG`(Portal) / `frontend/src/api/schoolSettings.js`(设置写入：纳入零 diff gate，不纳入逐 route 比对，必修⑥)；测试债 = 当前无任一守卫保证以上多方对齐，本计划反例矩阵 + frontend drift 探测消除该债。frontend drift 探测器 `_FRONTEND_DRIFT_PROBES` 须随新增 frontend drift 同步扩展（无探测器即 fail-closed，反例 #13a 保证）。

---

## Execution Handoff

实施前置（T3 流程）：本计划 commit 后须走 `codex-review plan`（engine 机器 verdict）生成 gates.json，PASS 后方可进入执行。
