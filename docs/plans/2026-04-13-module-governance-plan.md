<!-- pre-takeover: archived for history, not active spec -->
# edu-cloud 模块治理纲领 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.
>
> **T 级别：T3 / 禁止同会话执行** — 本 plan 必须在新会话中由 executor 执行。
>
> **设计依据：** `docs/plans/2026-04-13-module-governance-design.md`

**Goal:** 为 edu-cloud 建立项目级统一模块治理纲领——Layer 1 基线 + Layer 2 MODULE.md 契约 + Layer 3 自动派生 + Layer 4 机械守卫——禁止多版本并存与接口混乱，边开发边治理自愈式收敛。

**Architecture:** 四层治理模型。Opus 主导 P0 调研产出债务清单，P1 定义 MODULE.md 模板与聚合脚本，P2 在 grading/pipeline 试点落地，P3 上线 module_governance_guard hook 三档强制（block/ask/静默）。试点验证通过后自愈式扩展。

**Tech Stack:** Python 3.11（hook + aggregator）/ PyYAML / ast 标准库 / pytest / Claude Code hook 基础设施（hook_lib / tool_preference_ask Ask 范式 / commit_guards 合并调度模式）。

---

## 文件结构

**新建**：
- `edu-cloud/docs/governance/edu-cloud-module-baseline-2026-04-13.md` — P0 基线报告
- `edu-cloud/docs/governance/MODULE-template.md` — 模板（人读版）
- `edu-cloud/docs/governance/modules.yaml` — 聚合全局视图（P2 产出）
- `edu-cloud/docs/governance/dependency-graph.md` — 依赖图（P2 产出）
- `edu-cloud/docs/governance/debt-report.md` — 缺 MODULE.md 清单（P2 产出）
- `edu-cloud/scripts/governance/aggregate_modules.py` — 聚合脚本
- `edu-cloud/scripts/governance/__init__.py`
- `edu-cloud/tests/governance/test_aggregate_modules.py` — 聚合脚本测试
- `edu-cloud/tests/governance/test_module_governance_guard.py` — hook 测试
- `edu-cloud/src/edu_cloud/modules/grading/MODULE.md` — 试点 1
- `edu-cloud/src/edu_cloud/modules/pipeline/MODULE.md` — 试点 2
- `~/.claude/hooks/module_governance_guard.py` — 守卫 hook

**修改**：
- `~/.claude/hooks/commit_guards.py` — CHECKS 列表追加 module_governance_guard（Task 7）
- `~/.claude/CLAUDE.md` — 安全铁律段追加条目（Task 8，Gate 2 PASS 后）
- `edu-cloud/CLAUDE.md` — 「已完成设计」段追加本设计（Task 8，Gate 2 PASS 后）
- `edu-cloud/docs/plans/2026-04-13-module-governance-design.md` — 头部 `[实现完成]` 标记（Task 8）

**责任边界**：
- P0 产出在 `edu-cloud/docs/governance/`
- P1/P2 脚本在 `edu-cloud/scripts/governance/`
- P3 hook 在 `~/.claude/hooks/`（全局基础设施）

---

## Phase P0: 基线调研（Opus 主导，分批推进）

### Task 1: P0 全口径调研与债务清单

**角色说明：** 本 Task 由 Opus 4.6 作为 Executor 亲自执行调研（**不委派 subagent**），产出带证据的清单。判据路径：feedback_research_over_rules.md。

**Files:**
- Create: `edu-cloud/docs/governance/edu-cloud-module-baseline-2026-04-13.md`

- [ ] **Step 1: 候选缩小（机械扫描）**

Run (分别执行):
```bash
cd ~/edu-cloud
# 1. 模块列表
ls src/edu_cloud/modules/
# 2. 所有 ORM 类（找重复概念）
grep -rn "^class.*Base" src/edu_cloud/modules/ --include="*.py" | head -100
# 3. 所有 router mount（找路径重叠）
grep -rn "APIRouter\|include_router\|prefix=" src/edu_cloud/ --include="*.py" | head -100
# 4. 疑似废弃文件
find src/edu_cloud/ -type f \( -name "*_old*" -o -name "*_v1*" -o -name "*_deprecated*" -o -name "*_backup*" \)
# 5. services/ 列表（判断与 modules 职责重叠）
ls src/edu_cloud/services/
```

Expected: 产出候选列表，**不下判定**，仅用于缩小阅读范围。

- [ ] **Step 2: 分批阅读 + 交叉验证（Opus 主导）**

分 4 批完成，每批产出增量清单供用户批阅：

**Batch A（核心业务链路）**：paper / scan / pipeline / grading / marking / card
**Batch B（知识与学习）**：knowledge / knowledge_tree / adaptive / analytics / bank / homework
**Batch C（组织管理）**：exam / school / studio / conduct / student / profile / menu / calendar
**Batch D（横切层）**：services/ 12 文件 + ai/tools/ + api/ 路由汇总

每个模块阅读清单：
1. `modules/<X>/__init__.py`（导出什么）
2. 主 service 文件（核心动作）
3. router 文件（对外 API）
4. model 文件（owns 哪些表）

**交叉验证规则**（每个可疑冲突必须满足）：
- 证据 A：原文摘录（file:line）
- 证据 B：调用方 grep（谁在用）
- 证据 C：git log（是重写还是分工）
- 判定三选一：`真冲突` / `职责互补` / `历史债务`

- [ ] **Step 3: 写入基线报告**

每条冲突条目格式（强制）：
```markdown
### 冲突 #N: {一句话摘要}
- **位置 A**: `src/edu_cloud/modules/grading/dispatch.py:45`
- **位置 B**: `src/edu_cloud/modules/marking/dispatch.py:12`
- **证据**: {原文摘录 ≤3 行 + git log 关键行}
- **判定**: 真冲突 / 职责互补 / 历史债务
- **建议处置**: 去重 / 重命名 / 保留分工说明 / 标记 deprecated
- **影响面**: 调用方 N 处（列出 file:line）
- **用户决定**: [ ] approve / [ ] reject / [ ] defer
```

报告头部含：调研范围 / 已读模块清单 / 未读（跳过）清单与理由 / 统计（真冲突 N 条 / 职责互补 M 条 / 历史债务 K 条）。

- [ ] **Step 4: 用户批阅拍板**

将 Batch A-D 的增量清单依次交用户批阅，用户对每条 approve/reject/defer。approve 的条目进入 P2 落地时一并处置；reject 的标注理由；defer 的进入 debt-report.md。

- [ ] **Step 5: Commit baseline**

```bash
cd ~/edu-cloud
git add docs/governance/edu-cloud-module-baseline-2026-04-13.md
git commit -m "governance: P0 基线调研完成 — edu-cloud 模块债务清单"
```

**边界条件:**
- 空模块（目录存在但无 .py 文件）→ 期望: 报告标注"空占位，待实现"，不报为冲突
- 模块跨越 backend/frontend（如 card-editor）→ 期望: 仅评估后端部分，前端另议
- services/ 与 modules/ 同名（如 `paper_service.py` vs `modules/paper`）→ 期望: 判定"职责互补"并在报告中说明调用关系

**审查清单:**
- ✓ 每条冲突都有 3 类证据（原文/调用方/git log）
- ✓ 判定必须三选一，禁止"待定"
- ✗ 禁止在未读代码的情况下凭直觉下判定（L013 反向防御）
- ✗ 禁止把 triage 推给用户（用户只 approve/reject/defer，不分类）

**关键行为:** 本 Task 产出不改任何源码，只产出 1 份 markdown 报告；用户拍板 = 过 Gate。

---

## Phase P1: 纲领骨架（模板 + 聚合脚本）

### Task 2: MODULE.md 模板（人读版）

**Files:**
- Create: `edu-cloud/docs/governance/MODULE-template.md`

- [ ] **Step 1: 写模板（从 design §2 复制）**

内容完全对应 design §2 的模板示例，含 frontmatter 全字段 + 正文 5 段骨架 + 字段说明表。

- [ ] **Step 2: 添加「填写指引」段**

```markdown
## 填写指引

**最小合规门槛**（存量模块触碰时）：
1. frontmatter 必填字段全填
2. 正文「职责」段至少一句话
3. 其余段落可渐进补充

**字段填写规范**:
- `owns_tables`: 只列 `__tablename__` 明确定义在本模块的表
- `owns_routes`: 只列 FastAPI router 实际挂载的 prefix
- `depends_on.modules`: 只列 `from edu_cloud.modules.X import ...` 中的 X
- `depends_on.services`: 只列 `from edu_cloud.services.X import ...` 中的 X

**禁止**:
- 在 `owns_*` 里列其他模块拥有的资源（跨模块重复会被 hook 拒绝）
- 在正文「职责」段写"和 XX 相关的功能"空话
```

- [ ] **Step 3: Commit**

```bash
cd ~/edu-cloud
git add docs/governance/MODULE-template.md
git commit -m "governance: P1-1 添加 MODULE.md 模板"
```

**审查清单:**
- ✓ frontmatter 所有字段有说明
- ✓ 「禁止」段覆盖多版本并存风险点
- ✗ 禁止出现 TBD / "参考 xxx"（模板本身必须自洽）

---

### Task 3: 聚合脚本 aggregate_modules.py

**Files:**
- Create: `edu-cloud/scripts/governance/__init__.py`（空文件）
- Create: `edu-cloud/scripts/governance/aggregate_modules.py`
- Create: `edu-cloud/tests/governance/__init__.py`（空文件）
- Create: `edu-cloud/tests/governance/test_aggregate_modules.py`
- Create: `edu-cloud/tests/governance/fixtures/sample_module/MODULE.md`（测试用）

- [ ] **Step 1: Write the failing test**

```python
# tests/governance/test_aggregate_modules.py
import pytest
from pathlib import Path
from edu_cloud_scripts.governance.aggregate_modules import (
    parse_module_md,
    aggregate_all,
    detect_conflicts,
    ModuleGovernanceError,
)

FIXTURES = Path(__file__).parent / "fixtures"

def test_parse_module_md_returns_frontmatter():
    """parse_module_md 读取 MODULE.md 头部 YAML frontmatter。"""
    md_path = FIXTURES / "sample_module" / "MODULE.md"
    meta = parse_module_md(md_path)
    assert meta["name"] == "sample"
    assert meta["status"] == "active"
    assert "sample_tbl" in meta["owns_tables"]

def test_parse_module_md_missing_required_field_raises():
    """缺必填字段 → raise ModuleGovernanceError。"""
    bad = FIXTURES / "bad_missing_name"
    bad.mkdir(exist_ok=True)
    (bad / "MODULE.md").write_text("---\nstatus: active\n---\n# bad\n", encoding="utf-8")
    with pytest.raises(ModuleGovernanceError, match="missing.*name"):
        parse_module_md(bad / "MODULE.md")

def test_detect_conflicts_finds_duplicate_owns_tables():
    """两个模块声明同一张表 → 返回冲突记录。"""
    modules = [
        {"name": "a", "owns_tables": ["shared_tbl"], "owns_routes": []},
        {"name": "b", "owns_tables": ["shared_tbl"], "owns_routes": []},
    ]
    conflicts = detect_conflicts(modules)
    assert any(c["kind"] == "duplicate_table" and c["value"] == "shared_tbl" for c in conflicts)

def test_detect_conflicts_finds_duplicate_owns_routes():
    """两模块同一路由前缀 → 冲突。"""
    modules = [
        {"name": "a", "owns_tables": [], "owns_routes": ["/api/x"]},
        {"name": "b", "owns_tables": [], "owns_routes": ["/api/x"]},
    ]
    conflicts = detect_conflicts(modules)
    assert any(c["kind"] == "duplicate_route" and c["value"] == "/api/x" for c in conflicts)

def test_aggregate_all_writes_yaml_and_debt_report(tmp_path):
    """aggregate_all 产出 modules.yaml + debt-report.md。"""
    # 准备假 modules 目录（1 有 MODULE.md、1 缺 MODULE.md）
    modules_dir = tmp_path / "modules"
    (modules_dir / "alpha").mkdir(parents=True)
    (modules_dir / "alpha" / "MODULE.md").write_text(
        FIXTURES.joinpath("sample_module", "MODULE.md").read_text(encoding="utf-8").replace("sample", "alpha"),
        encoding="utf-8",
    )
    (modules_dir / "beta").mkdir(parents=True)
    (modules_dir / "beta" / "__init__.py").touch()  # 无 MODULE.md

    out_dir = tmp_path / "docs" / "governance"
    aggregate_all(modules_dir=modules_dir, out_dir=out_dir)

    assert (out_dir / "modules.yaml").exists()
    assert (out_dir / "debt-report.md").exists()
    assert (out_dir / "dependency-graph.md").exists()

    debt = (out_dir / "debt-report.md").read_text(encoding="utf-8")
    assert "beta" in debt  # 缺 MODULE.md 的模块被记录
```

- [ ] **Step 2: 创建 fixture**

```bash
mkdir -p ~/edu-cloud/tests/governance/fixtures/sample_module
cat > ~/edu-cloud/tests/governance/fixtures/sample_module/MODULE.md <<'EOF'
---
name: sample
status: active
owner: test
layer: business
owns_tables: [sample_tbl]
owns_routes: [/api/sample]
exposes:
  services: [do_thing]
  events: []
depends_on:
  modules: []
  services: []
  ai_tools: []
created: 2026-04-13
last_reviewed: 2026-04-13
design_docs: []
---
# sample 模块

## 职责
测试用占位模块。
EOF
```

- [ ] **Step 3: Run test to verify failures**

```bash
cd ~/edu-cloud && pytest tests/governance/test_aggregate_modules.py -v
```
Expected: ImportError / ModuleNotFoundError（脚本尚未实现）。

- [ ] **Step 4: 实现 aggregate_modules.py**

```python
# scripts/governance/aggregate_modules.py
"""
edu-cloud 模块治理聚合脚本

读取 src/edu_cloud/modules/*/MODULE.md 的 YAML frontmatter，
产出 docs/governance/{modules.yaml, dependency-graph.md, debt-report.md}。

禁止手写 modules.yaml —— 单一真源在 MODULE.md。
"""
from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable
import yaml

REQUIRED_FIELDS = ["name", "status", "owner", "layer", "owns_tables", "owns_routes", "exposes", "depends_on"]
VALID_STATUS = {"active", "deprecated", "experimental"}
VALID_LAYER = {"business", "infrastructure", "cross-cutting"}


class ModuleGovernanceError(ValueError):
    """MODULE.md 格式或内容违反纲领。"""


def parse_module_md(md_path: Path) -> dict[str, Any]:
    """解析 MODULE.md frontmatter。缺必填字段 / 枚举非法 → 抛错。"""
    text = md_path.read_text(encoding="utf-8")
    if not text.startswith("---\n"):
        raise ModuleGovernanceError(f"{md_path}: missing frontmatter")
    end = text.find("\n---\n", 4)
    if end < 0:
        raise ModuleGovernanceError(f"{md_path}: frontmatter not closed")
    try:
        meta = yaml.safe_load(text[4:end]) or {}
    except yaml.YAMLError as e:
        raise ModuleGovernanceError(f"{md_path}: YAML parse error: {e}") from e

    for field in REQUIRED_FIELDS:
        if field not in meta:
            raise ModuleGovernanceError(f"{md_path}: missing required field '{field}'")
    if meta["status"] not in VALID_STATUS:
        raise ModuleGovernanceError(f"{md_path}: invalid status '{meta['status']}'")
    if meta["layer"] not in VALID_LAYER:
        raise ModuleGovernanceError(f"{md_path}: invalid layer '{meta['layer']}'")
    return meta


def detect_conflicts(modules: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """返回跨模块 owns_tables / owns_routes 冲突列表。"""
    table_owner: dict[str, str] = {}
    route_owner: dict[str, str] = {}
    conflicts: list[dict[str, Any]] = []
    for m in modules:
        for t in m.get("owns_tables") or []:
            if t in table_owner:
                conflicts.append({"kind": "duplicate_table", "value": t, "owners": [table_owner[t], m["name"]]})
            else:
                table_owner[t] = m["name"]
        for r in m.get("owns_routes") or []:
            if r in route_owner:
                conflicts.append({"kind": "duplicate_route", "value": r, "owners": [route_owner[r], m["name"]]})
            else:
                route_owner[r] = m["name"]
    return conflicts


def _render_dep_graph(modules: list[dict[str, Any]]) -> str:
    """Mermaid flowchart TD。"""
    lines = ["# edu-cloud 模块依赖图\n", "> 自动生成，禁止手写。源：各模块 MODULE.md frontmatter。\n", "```mermaid", "flowchart TD"]
    for m in modules:
        for dep in (m.get("depends_on") or {}).get("modules") or []:
            lines.append(f"  {m['name']} --> {dep}")
    lines.append("```\n")
    return "\n".join(lines)


def _render_debt(modules_dir: Path, covered: set[str]) -> str:
    """列出 modules/ 下缺 MODULE.md 的子目录。"""
    debt = []
    for child in sorted(modules_dir.iterdir()):
        if child.is_dir() and child.name != "__pycache__" and not child.name.startswith("_"):
            if child.name not in covered:
                debt.append(child.name)
    lines = ["# MODULE.md 债务清单\n", "> 自动生成。以下模块缺 MODULE.md，下次触碰时 hook 会 ask。\n"]
    if not debt:
        lines.append("_无债务——所有模块已合规。_\n")
    else:
        for name in debt:
            lines.append(f"- `src/edu_cloud/modules/{name}/`")
    return "\n".join(lines) + "\n"


def aggregate_all(modules_dir: Path, out_dir: Path) -> dict[str, Any]:
    """主入口。返回统计信息。"""
    out_dir.mkdir(parents=True, exist_ok=True)
    modules: list[dict[str, Any]] = []
    covered: set[str] = set()
    for child in sorted(modules_dir.iterdir()):
        if not child.is_dir() or child.name.startswith("_") or child.name == "__pycache__":
            continue
        md = child / "MODULE.md"
        if md.exists():
            meta = parse_module_md(md)
            modules.append(meta)
            covered.add(meta["name"])
    conflicts = detect_conflicts(modules)

    (out_dir / "modules.yaml").write_text(
        yaml.safe_dump({"modules": modules, "conflicts": conflicts}, allow_unicode=True, sort_keys=False),
        encoding="utf-8",
    )
    (out_dir / "dependency-graph.md").write_text(_render_dep_graph(modules), encoding="utf-8")
    (out_dir / "debt-report.md").write_text(_render_debt(modules_dir, covered), encoding="utf-8")
    return {"modules": len(modules), "conflicts": len(conflicts), "debt": len([c for c in modules_dir.iterdir() if c.is_dir()]) - len(covered)}


if __name__ == "__main__":
    import sys
    repo = Path(__file__).resolve().parents[2]
    stats = aggregate_all(repo / "src" / "edu_cloud" / "modules", repo / "docs" / "governance")
    print(f"Aggregated: {stats}")
    sys.exit(1 if stats["conflicts"] > 0 else 0)
```

- [ ] **Step 5: 配置 pytest 可 import scripts**

Modify: `edu-cloud/pyproject.toml` — 在 `[tool.pytest.ini_options]` 追加 `pythonpath = ["scripts", "src"]`，并添加别名包指向（或 test 里用 sys.path.insert）。

为简化不改 pyproject，改测试 import 方式：

```python
# 测试顶部替换为：
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts" / "governance"))
from aggregate_modules import parse_module_md, aggregate_all, detect_conflicts, ModuleGovernanceError
```

- [ ] **Step 6: Run tests to verify all pass**

```bash
cd ~/edu-cloud && pytest tests/governance/test_aggregate_modules.py -v
```
Expected: 5 passed.

- [ ] **Step 7: Commit**

```bash
cd ~/edu-cloud
git add scripts/governance/ tests/governance/
git commit -m "governance: P1-2 聚合脚本 aggregate_modules.py + 5 tests"
```

**边界条件:**
- 空 modules/ 目录 → 期望: 产出空 yaml + "无债务"debt-report，不抛错
- MODULE.md frontmatter YAML 语法错误 → 期望: raise ModuleGovernanceError，消息含路径
- 模块目录含 `__pycache__` / `_internal` → 期望: 跳过，不报债务

**测试契约:**
1. 正常 MODULE.md 解析
   - 入口: `parse_module_md(path)` → dict
   - 反例: 错误实现会漏校验必填字段或 status 枚举——test_parse_module_md_missing_required_field_raises 捕获
   - 边界: 缺 name / YAML 错 / frontmatter 未关
   - 回归: N/A（新功能）
   - 命令: `pytest tests/governance/test_aggregate_modules.py::test_parse_module_md_returns_frontmatter -v`
2. 冲突检测
   - 入口: `detect_conflicts([m1, m2])` → list
   - 反例: 错误实现可能只查表不查路由——test_detect_conflicts_finds_duplicate_owns_routes 捕获
   - 边界: 单模块两张相同表 / 空列表 / 三模块同一路由
   - 回归: L015 核心约束
   - 命令: `pytest tests/governance/test_aggregate_modules.py::test_detect_conflicts_finds_duplicate_owns_tables tests/governance/test_aggregate_modules.py::test_detect_conflicts_finds_duplicate_owns_routes -v`
3. 端到端聚合
   - 入口: `aggregate_all(modules_dir, out_dir)`
   - 反例: 错误实现可能漏产 debt-report——test_aggregate_all_writes_yaml_and_debt_report 捕获（断言 beta 在 debt 中）
   - 边界: 部分模块有 MODULE.md / 部分无
   - 回归: N/A
   - 命令: `pytest tests/governance/test_aggregate_modules.py::test_aggregate_all_writes_yaml_and_debt_report -v`
4. **CLI 入口级验证（F004 修正）**
   - 入口: `subprocess.run([sys.executable, "scripts/governance/aggregate_modules.py"], cwd=repo)`
   - 反例: 错误实现可能 import path 断裂或 __main__ 块漏调 aggregate_all——只测函数级通过但 CLI 失败
   - 边界: 有冲突时退出码 1 / 无冲突退出码 0 / 空 modules/ 不崩
   - 回归: 防打包路径/shebang/main 块回退
   - 命令: `pytest tests/governance/test_aggregate_modules.py::test_cli_entry_produces_outputs -v`
   - 测试实现要点：
     ```python
     def test_cli_entry_produces_outputs(tmp_path):
         """subprocess 跑 aggregate_modules.py 作为 CLI，验证 stdout + exit code + 产物文件。"""
         import subprocess, sys, shutil
         repo = tmp_path
         (repo / "src/edu_cloud/modules/alpha").mkdir(parents=True)
         shutil.copy(FIXTURES / "sample_module" / "MODULE.md", repo / "src/edu_cloud/modules/alpha/MODULE.md")
         # 修正 alpha 模块名
         p = repo / "src/edu_cloud/modules/alpha/MODULE.md"
         p.write_text(p.read_text(encoding="utf-8").replace("name: sample", "name: alpha").replace("sample_tbl", "alpha_tbl").replace("/api/sample", "/api/alpha"), encoding="utf-8")
         (repo / "docs/governance").mkdir(parents=True)
         script = Path(__file__).resolve().parents[2] / "scripts" / "governance" / "aggregate_modules.py"
         result = subprocess.run([sys.executable, str(script)], cwd=repo, capture_output=True, text=True)
         assert result.returncode == 0, result.stderr
         assert (repo / "docs/governance/modules.yaml").exists()
         assert "Aggregated" in result.stdout
     ```

**审查清单:**
- ✓ 所有测试在 fresh repo clone 后可独立跑通（无外部依赖）
- ✓ ModuleGovernanceError 消息含文件路径
- ✗ 禁止用 eval / exec 解析 YAML（安全）
- ✗ 禁止聚合脚本静默吞异常（必须 raise）

---

## Phase P2: 试点落地（grading + pipeline）

### Task 4: grading 模块 MODULE.md

**Files:**
- Create: `edu-cloud/src/edu_cloud/modules/grading/MODULE.md`

- [ ] **Step 1: 阅读 grading 模块真实代码**

```bash
cd ~/edu-cloud
ls src/edu_cloud/modules/grading/
cat src/edu_cloud/modules/grading/__init__.py
grep -rn "__tablename__" src/edu_cloud/modules/grading/ --include="*.py"
grep -rn "APIRouter\|prefix=" src/edu_cloud/modules/grading/ --include="*.py"
grep -rn "^from edu_cloud\." src/edu_cloud/modules/grading/ --include="*.py" | sort -u
```

- [ ] **Step 2: 写 MODULE.md（基于真实代码）**

**铁律（F003 修正）**：frontmatter 字段值必须以 Step 1 读出的真实代码为准——**禁止**凭 `docs/plans/2026-04-12-grading-dispatch-design.md` 的叙述预设边界。代码实情优先于设计叙述。

基于 Step 1 输出列出：
- `owns_tables`: Step 1 `__tablename__` grep 的真实列表
- `owns_routes`: Step 1 `APIRouter(prefix=...)` 的真实 prefix
- `depends_on.modules`: Step 1 `from edu_cloud.modules.X` 真实 import 的 X

正文段落（Executor 自行撰写）：
- **职责**：一句话——根据真实 routes/tables/events 的职责综合
- **边界**：做什么（基于代码证据） / 不做什么（由代码边界反推）
- **使用方式**：前端/上游模块如何调用（基于真实 router 端点）
- **数据流**：基于真实 service 函数输入/输出
- **变更历史**：仅列对外契约变更

- [ ] **Step 3: 手动跑 aggregate 脚本验证**

```bash
cd ~/edu-cloud && python scripts/governance/aggregate_modules.py
```
Expected: exit 0（无冲突，因为 pipeline 的 MODULE.md 尚未写，不会冲突）。

- [ ] **Step 4: Commit**

```bash
cd ~/edu-cloud
git add src/edu_cloud/modules/grading/MODULE.md
git commit -m "governance: P2-1 grading 模块 MODULE.md"
```

**审查清单:**
- ✓ frontmatter `owns_tables` 与 `__tablename__` 实际值一致
- ✓ `owns_routes` 与 FastAPI router 实际 prefix 一致
- ✓ `depends_on.modules` 覆盖所有 `from edu_cloud.modules.X import` 中的 X
- ✗ 禁止在「职责」段写"与阅卷相关的功能"这种空话

**边界条件:**
- grading 若未挂载 router（仅内部调度）→ `owns_routes: []`
- grading 若无自己的表（纯逻辑）→ `owns_tables: []`
- 被 frontmatter 校验拒绝 → 修正字段重试，**禁止**降低校验标准

---

### Task 5: pipeline 模块 MODULE.md

**Files:**
- Create: `edu-cloud/src/edu_cloud/modules/pipeline/MODULE.md`

- [ ] **Step 1: 阅读 pipeline 模块真实代码**

同 Task 4 Step 1，替换 grading → pipeline。

- [ ] **Step 2: 写 MODULE.md（基于真实代码）**

**铁律（F003 修正）**：同 Task 4 Step 2 的铁律——代码实情优先。pipeline 与 grading 的实际职责边界由 Step 1 的 routes/tables/service 函数推出，不可假设"pipeline=执行 / grading=调度"。

**冲突检测前提**：Task 4 + Task 5 的 `owns_tables` / `owns_routes` 必须不重叠。如果 Step 1 发现两模块实际声明相同资源 → 这本身就是 L015 债务，记入 baseline.md defer，本 Task 暂停并上报用户决策（不要为了合规捏造归属）。

- [ ] **Step 3: 跑 aggregate 脚本验证无冲突**

```bash
cd ~/edu-cloud && python scripts/governance/aggregate_modules.py
```
Expected: exit 0；`docs/governance/modules.yaml` 含 grading + pipeline 两条；`dependency-graph.md` 反映 Step 1 读到的**真实**模块依赖（方向由代码决定：可能 grading→pipeline、pipeline→grading、双向、或无直接边——不预设）。

- [ ] **Step 4: Commit 含自动产出**

```bash
cd ~/edu-cloud
git add src/edu_cloud/modules/pipeline/MODULE.md docs/governance/modules.yaml docs/governance/dependency-graph.md docs/governance/debt-report.md
git commit -m "governance: P2-2 pipeline 模块 MODULE.md + 聚合产物首版"
```

**审查清单:**
- ✓ grading 和 pipeline 的 owns_* 不重叠（冲突检测过）
- ✓ grading.depends_on.modules 含 pipeline（或反之，按真实依赖）
- ✗ 禁止把 grading 的表"窃为己有"

---

## Phase P3: 守卫 hook（module_governance_guard）

### Task 6: module_governance_guard.py 核心实现

**Files:**
- Create: `~/.claude/hooks/module_governance_guard.py`
- Create: `edu-cloud/tests/governance/test_module_governance_guard.py`

- [ ] **Step 1: Write failing tests（F001/F002/F004/F006/F007 修正）**

测试覆盖:
- 纯函数单元: `check_new_module(files, repo)` / `check_ownership_conflicts(modules)` / `check_touched_legacy(files, diff, repo)` / `parse_diff_line_counts(diff)`
- **真实 staged_info 契约**: `{"files": [...], "diff": "..."}`（F006 修正）
- **F007 反退化**: 工作区存在但未 staged 的 MODULE.md 必须被 block
- **入口级测试（F004）**: `check(data, session_state, staged_info) -> dict | None` 完整链路

```python
# tests/governance/test_module_governance_guard.py
import subprocess
from pathlib import Path
from unittest.mock import MagicMock
import sys
sys.path.insert(0, str(Path.home() / ".claude" / "hooks"))
import module_governance_guard as g


def _git_init(repo: Path):
    subprocess.run(["git", "init", "-q"], cwd=repo, check=True)
    subprocess.run(["git", "config", "user.email", "t@t"], cwd=repo, check=True)
    subprocess.run(["git", "config", "user.name", "t"], cwd=repo, check=True)


def _valid_frontmatter(name: str) -> str:
    """生成通过 parse_module_md 校验的最小合法 MODULE.md（F008）。"""
    return (
        f"---\n"
        f"name: {name}\n"
        f"status: active\n"
        f"owner: test\n"
        f"layer: business\n"
        f"owns_tables: []\n"
        f"owns_routes: []\n"
        f"exposes:\n  services: []\n  events: []\n"
        f"depends_on:\n  modules: []\n  services: []\n  ai_tools: []\n"
        f"---\n# {name}\n\n## 职责\ntest.\n"
    )


def _setup_aggregate_script(repo: Path):
    """为 check_new_module F008 校验提供 aggregate_modules 脚本。"""
    scripts_dir = repo / "scripts" / "governance"
    scripts_dir.mkdir(parents=True, exist_ok=True)
    # 复制真实 aggregate_modules.py（假定已在 scripts/governance 下；测试前置 Task 3 已实现）
    real = Path(__file__).resolve().parents[2] / "scripts" / "governance" / "aggregate_modules.py"
    if real.exists():
        (scripts_dir / "aggregate_modules.py").write_text(real.read_text(encoding="utf-8"), encoding="utf-8")
        (scripts_dir / "__init__.py").touch()


def _git_init_with_module(repo: Path, module_name: str, include_module_md: bool = False):
    _git_init(repo)
    _setup_aggregate_script(repo)
    mdir = repo / "src/edu_cloud/modules" / module_name
    mdir.mkdir(parents=True)
    (mdir / "__init__.py").write_text("", encoding="utf-8")
    if include_module_md:
        (mdir / "MODULE.md").write_text(_valid_frontmatter(module_name), encoding="utf-8")
    subprocess.run(["git", "add", "."], cwd=repo, check=True)
    subprocess.run(["git", "commit", "-m", "init", "-q"], cwd=repo, check=True)


def _sample_diff(path: str, added: int, deleted: int) -> str:
    """构造最小 unified diff。"""
    plus = "\n".join(f"+line{i}" for i in range(added))
    minus = "\n".join(f"-line{i}" for i in range(deleted))
    body = "\n".join([x for x in [plus, minus] if x])
    return (
        f"diff --git a/{path} b/{path}\n"
        f"--- a/{path}\n"
        f"+++ b/{path}\n"
        f"@@ -0,0 +1 @@\n"
        f"{body}\n"
    )


# --- 单元：parse_diff_line_counts ---
def test_parse_diff_line_counts_basic():
    diff = _sample_diff("a/b.py", added=3, deleted=2)
    r = g.parse_diff_line_counts(diff)
    assert r["a/b.py"]["added"] == 3
    assert r["a/b.py"]["deleted"] == 2


def test_parse_diff_line_counts_multi_file():
    diff = _sample_diff("x.py", 5, 0) + _sample_diff("y.py", 0, 4)
    r = g.parse_diff_line_counts(diff)
    assert r["x.py"] == {"added": 5, "deleted": 0}
    assert r["y.py"] == {"added": 0, "deleted": 4}


def test_parse_diff_line_counts_ignores_headers():
    """+++/--- 头行不算 added/deleted。"""
    diff = _sample_diff("f.py", 2, 0)
    r = g.parse_diff_line_counts(diff)
    assert r["f.py"]["added"] == 2  # 不含 +++


# --- 单元：check_new_module（files 契约 + F007） ---
def test_new_module_without_module_md_blocks(tmp_path):
    _git_init(tmp_path)
    (tmp_path / "src/edu_cloud/modules/newmod").mkdir(parents=True)
    files = ["src/edu_cloud/modules/newmod/__init__.py"]
    result = g.check_new_module(files, tmp_path)
    assert result["decision"] == "block"
    assert "newmod" in result["reason"]


def test_new_module_with_valid_module_md_staged_passes(tmp_path):
    _git_init(tmp_path)
    _setup_aggregate_script(tmp_path)
    mdir = tmp_path / "src/edu_cloud/modules/newmod"
    mdir.mkdir(parents=True)
    (mdir / "MODULE.md").write_text(_valid_frontmatter("newmod"), encoding="utf-8")
    files = [
        "src/edu_cloud/modules/newmod/__init__.py",
        "src/edu_cloud/modules/newmod/MODULE.md",
    ]
    result = g.check_new_module(files, tmp_path)
    assert result is None


def test_new_module_module_md_in_workspace_but_not_staged_still_blocks(tmp_path):
    """F007 反退化: MODULE.md 在工作区但未 git add → 仍 block。"""
    _git_init(tmp_path)
    _setup_aggregate_script(tmp_path)
    (tmp_path / "src/edu_cloud/modules/newmod").mkdir(parents=True)
    (tmp_path / "src/edu_cloud/modules/newmod/MODULE.md").write_text(_valid_frontmatter("newmod"), encoding="utf-8")
    files = ["src/edu_cloud/modules/newmod/__init__.py"]  # MODULE.md 不在 staged 列表
    result = g.check_new_module(files, tmp_path)
    assert result is not None, "F007 退化：工作区存在被误放行"
    assert result["decision"] == "block"


def test_new_module_with_invalid_module_md_missing_field_blocks(tmp_path):
    """F008: staged MODULE.md 缺必填字段 → block (不是 allow)。"""
    _git_init(tmp_path)
    _setup_aggregate_script(tmp_path)
    mdir = tmp_path / "src/edu_cloud/modules/newmod"
    mdir.mkdir(parents=True)
    # 只有 name，缺 status/owner/layer/owns/exposes/depends_on
    (mdir / "MODULE.md").write_text("---\nname: newmod\n---\n# x\n", encoding="utf-8")
    files = [
        "src/edu_cloud/modules/newmod/__init__.py",
        "src/edu_cloud/modules/newmod/MODULE.md",
    ]
    result = g.check_new_module(files, tmp_path)
    assert result is not None, "F008 退化：非法 frontmatter 被放行"
    assert result["decision"] == "block"
    assert "newmod" in result["reason"]


def test_new_module_with_invalid_yaml_blocks(tmp_path):
    """F008: staged MODULE.md YAML 语法错误 → block。"""
    _git_init(tmp_path)
    _setup_aggregate_script(tmp_path)
    mdir = tmp_path / "src/edu_cloud/modules/newmod"
    mdir.mkdir(parents=True)
    (mdir / "MODULE.md").write_text("---\nname: [unclosed\n---\n", encoding="utf-8")
    files = [
        "src/edu_cloud/modules/newmod/__init__.py",
        "src/edu_cloud/modules/newmod/MODULE.md",
    ]
    result = g.check_new_module(files, tmp_path)
    assert result is not None
    assert result["decision"] == "block"


def test_check_entry_blocks_on_invalid_existing_module_md(tmp_path):
    """F008: 存量模块中任一 MODULE.md 非法 → loader 报错 → check() block。"""
    _git_init_with_module(tmp_path, "legacy", include_module_md=True)
    # 故意把已有 MODULE.md 改为非法
    md = tmp_path / "src/edu_cloud/modules/legacy/MODULE.md"
    md.write_text("---\nname: legacy\n---\n", encoding="utf-8")  # 缺字段
    data = {"cwd": str(tmp_path), "tool_input": {"command": "git commit -m x"}}
    staged_info = {
        "files": ["src/edu_cloud/modules/legacy/service.py"],
        "diff": _sample_diff("src/edu_cloud/modules/legacy/service.py", 1, 0),
    }
    result = g.check(data, MagicMock(), staged_info=staged_info)
    assert result is not None
    assert result["decision"] == "block"
    assert "解析失败" in result["reason"] or "legacy" in result["reason"]


def test_legacy_module_without_module_md_not_blocked_by_new_check(tmp_path):
    """F002 反退化: 存量模块缺 MODULE.md 不应被 check_new_module 拦截。"""
    _git_init_with_module(tmp_path, "legacy", include_module_md=False)
    files = ["src/edu_cloud/modules/legacy/service.py"]
    assert g.check_new_module(files, tmp_path) is None


# --- 单元：owns 冲突 ---
def test_duplicate_owns_tables_blocks():
    modules = [
        {"name": "a", "owns_tables": ["shared"], "owns_routes": []},
        {"name": "b", "owns_tables": ["shared"], "owns_routes": []},
    ]
    result = g.check_ownership_conflicts(modules)
    assert result["decision"] == "block"
    assert "shared" in result["reason"]


def test_same_module_duplicate_owns_not_conflict():
    modules = [{"name": "a", "owns_tables": ["t", "t"], "owns_routes": []}]
    assert g.check_ownership_conflicts(modules) is None


# --- 单元：check_touched_legacy（files + diff 契约） ---
def test_large_modification_without_module_md_asks(tmp_path):
    _git_init_with_module(tmp_path, "legacy", include_module_md=False)
    path = "src/edu_cloud/modules/legacy/service.py"
    diff = _sample_diff(path, added=40, deleted=20)
    result = g.check_touched_legacy([path], diff, tmp_path)
    assert result["decision"] == "ask"
    assert "legacy" in result["reason"]


def test_small_modification_does_not_ask(tmp_path):
    _git_init_with_module(tmp_path, "legacy", include_module_md=False)
    path = "src/edu_cloud/modules/legacy/service.py"
    diff = _sample_diff(path, added=3, deleted=2)
    assert g.check_touched_legacy([path], diff, tmp_path) is None


# --- 入口级（F004/F006 修正）：check() 消费真实 staged_info ---
def test_hook_entry_blocks_on_new_module_without_module_md(tmp_path):
    _git_init(tmp_path)
    (tmp_path / "src/edu_cloud/modules/newmod").mkdir(parents=True)
    data = {"cwd": str(tmp_path), "tool_input": {"command": "git commit -m test"}}
    staged_info = {
        "files": ["src/edu_cloud/modules/newmod/__init__.py"],
        "diff": _sample_diff("src/edu_cloud/modules/newmod/__init__.py", 1, 0),
    }
    result = g.check(data, MagicMock(), staged_info=staged_info)
    assert result is not None
    assert result["decision"] == "block"
    assert "newmod" in result["reason"]


def test_hook_entry_asks_on_large_legacy_touch(tmp_path):
    _git_init_with_module(tmp_path, "legacy", include_module_md=False)
    path = "src/edu_cloud/modules/legacy/service.py"
    data = {"cwd": str(tmp_path), "tool_input": {"command": "git commit -m x"}}
    staged_info = {"files": [path], "diff": _sample_diff(path, 40, 20)}
    result = g.check(data, MagicMock(), staged_info=staged_info)
    assert result is not None
    assert result["decision"] == "ask"


def test_hook_entry_allows_non_edu_cloud_repo(tmp_path):
    data = {"cwd": "/some/other/repo", "tool_input": {"command": "git commit -m x"}}
    result = g.check(data, MagicMock(), staged_info={"files": [], "diff": ""})
    assert result is None


def test_hook_entry_allows_non_git_commit_command(tmp_path):
    _git_init(tmp_path)
    data = {"cwd": str(tmp_path), "tool_input": {"command": "ls -la"}}
    result = g.check(data, MagicMock(), staged_info={"files": ["x"], "diff": ""})
    assert result is None


# --- F009: 派生产物过期检测 ---
def test_derived_products_stale_blocks(tmp_path):
    """F009: MODULE.md 变更但 modules.yaml 未刷新 → block。"""
    _git_init_with_module(tmp_path, "alpha", include_module_md=True)
    # docs/governance/ 存在但派生产物是陈旧的（空）
    out = tmp_path / "docs/governance"
    out.mkdir(parents=True, exist_ok=True)
    (out / "modules.yaml").write_text("stale: true\n", encoding="utf-8")
    (out / "dependency-graph.md").write_text("old\n", encoding="utf-8")
    (out / "debt-report.md").write_text("old\n", encoding="utf-8")
    files = ["src/edu_cloud/modules/alpha/MODULE.md"]
    result = g.check_derived_products_fresh(tmp_path, files)
    assert result is not None, "F009 退化：派生产物漂移未被检测"
    assert result["decision"] == "block"
    assert "modules.yaml" in result["reason"]


def test_derived_products_fresh_passes(tmp_path):
    """派生产物与 MODULE.md 同步 → allow。"""
    _git_init_with_module(tmp_path, "alpha", include_module_md=True)
    out = tmp_path / "docs/governance"
    out.mkdir(parents=True, exist_ok=True)
    # 调用 aggregate 生成与当前 MODULE.md 匹配的产物
    import aggregate_modules  # 已由 _setup_aggregate_script 放在 sys.path
    aggregate_modules.aggregate_all(tmp_path / "src/edu_cloud/modules", out)
    files = ["src/edu_cloud/modules/alpha/MODULE.md"]
    assert g.check_derived_products_fresh(tmp_path, files) is None


def test_derived_products_check_skipped_when_no_governance_dir(tmp_path):
    """首次搭建：docs/governance/ 不存在 → 不 block（设施未就绪）。"""
    _git_init_with_module(tmp_path, "alpha", include_module_md=True)
    files = ["src/edu_cloud/modules/alpha/MODULE.md"]
    assert g.check_derived_products_fresh(tmp_path, files) is None


# --- Kill switch 入口级 ---
def test_kill_switch_disables_entry(monkeypatch, tmp_path):
    monkeypatch.setenv("EDU_GOVERNANCE_GUARD_DISABLED", "1")
    _git_init(tmp_path)
    (tmp_path / "src/edu_cloud/modules/newmod").mkdir(parents=True)
    data = {"cwd": str(tmp_path), "tool_input": {"command": "git commit -m x"}}
    staged_info = {
        "files": ["src/edu_cloud/modules/newmod/__init__.py"],
        "diff": _sample_diff("src/edu_cloud/modules/newmod/__init__.py", 1, 0),
    }
    assert g.check(data, MagicMock(), staged_info=staged_info) is None
```

- [ ] **Step 2: Run tests to verify failures**

```bash
cd ~/edu-cloud && pytest tests/governance/test_module_governance_guard.py -v
```
Expected: all FAIL (ImportError / AttributeError)。

- [ ] **Step 3: 实现 module_governance_guard.py（F001+F002+F006+F007 修正）**

**关键契约（实读 commit_guards.py 验证）**：
- 签名: `check(data, session_state, staged_info=None) -> dict | None`（与其他子 guard 一致）
- `staged_info` **真实结构**: `{"files": list[str], "diff": str}`（commit_guards.py:99）——非 `{paths, stats}`
  - `files`: `git diff --cached --name-only` 的逐行列表
  - `diff`: `git diff --cached -U0` 的完整 unified diff 字符串
- 行数统计必须从 `diff` 解析（按 `+`/`-` 前缀行，排除 `+++`/`---` 头），不能指望 dispatcher 预聚合

**返回值语义**:
- 返回 `None` = allow（不干预）
- 返回 `{"decision": "block", "reason": "..."}` = 硬阻断
- 返回 `{"decision": "ask", "reason": "..."}` = 软询问

**新模块判定铁律（F002+F007）**：
- 新旧判定: `git ls-tree HEAD <path>` 为唯一真源，HEAD 不含该目录 → 新模块
- MODULE.md 合规证据: **只认 staged files 列表**，工作区存在但未 git add 不算（F007）

```python
#!/usr/bin/env python3
"""
edu-cloud 模块治理守卫 (commit_guards 子 guard)

接线契约（实读 ~/.claude/hooks/commit_guards.py:82-99 验证）：
- 由 commit_guards.py 在 git commit 时调用
- 签名: check(data, session_state, staged_info=None) -> dict | None
  - None = allow；dict 含 decision (block/ask) + reason
- staged_info 结构: {"files": list[str], "diff": str}
  - files: git diff --cached --name-only 逐行
  - diff:  git diff --cached -U0 完整 unified diff

当前 Phase 检查（design §4 P3 渐进开启）:
- block: 1 新建模块缺 MODULE.md, 3 owns_tables 冲突, 4 owns_routes 冲突
- ask:   2 触碰存量 ≥50 行缺 MODULE.md
- 未上: 5 (import 登记), 6 (MODULE.md vs 代码)

KILL_SWITCH: EDU_GOVERNANCE_GUARD_DISABLED=1
"""
from __future__ import annotations
import os
import re
import subprocess
import sys
from pathlib import Path
from typing import Any

MODULES_DIR = "src/edu_cloud/modules"
LARGE_MODIFY_THRESHOLD = 50
EDU_CLOUD_MARKER = "edu-cloud"


def _kill_switch() -> bool:
    return os.environ.get("EDU_GOVERNANCE_GUARD_DISABLED") == "1"


def _is_edu_cloud(cwd: str | Path) -> bool:
    p = Path(cwd)
    return p.name == EDU_CLOUD_MARKER or (p / "src" / "edu_cloud").exists()


def _module_name_from_path(path: str) -> str | None:
    normalized = Path(path).as_posix().split("/")
    if len(normalized) < 5:
        return None
    if "/".join(normalized[:3]) != MODULES_DIR:
        return None
    return normalized[3]


def _dir_exists_in_head(repo: Path, rel_dir: str) -> bool:
    """git ls-tree -d HEAD <rel_dir>：HEAD 含该目录返回 True。"""
    try:
        r = subprocess.run(
            ["git", "-C", str(repo), "ls-tree", "-d", "HEAD", rel_dir],
            capture_output=True, text=True, timeout=5,
        )
        return r.returncode == 0 and bool(r.stdout.strip())
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
        return False  # 无 HEAD（首次 commit）→ 按"新建"保守判定


def parse_diff_line_counts(diff: str) -> dict[str, dict[str, int]]:
    """
    解析 unified diff，返回 {path: {"added": n, "deleted": n}}。

    规则:
    - `diff --git a/... b/...` 切换当前文件（以 b/ 为准，新路径）
    - `+` 开头的行（非 `+++`）= added
    - `-` 开头的行（非 `---`）= deleted
    """
    result: dict[str, dict[str, int]] = {}
    current: str | None = None
    DIFF_HEADER_RE = re.compile(r"^diff --git a/(.*?) b/(.*)$")
    for line in diff.splitlines():
        m = DIFF_HEADER_RE.match(line)
        if m:
            current = m.group(2).strip()
            result.setdefault(current, {"added": 0, "deleted": 0})
            continue
        if current is None:
            continue
        if line.startswith("+++") or line.startswith("---"):
            continue
        if line.startswith("+"):
            result[current]["added"] += 1
        elif line.startswith("-"):
            result[current]["deleted"] += 1
    return result


def _import_aggregate_module(repo: Path):
    """导入 aggregate_modules（共享 parse_module_md 契约）。失败 raise。"""
    scripts_dir = str(repo / "scripts" / "governance")
    if scripts_dir not in sys.path:
        sys.path.insert(0, scripts_dir)
    import aggregate_modules  # type: ignore
    return aggregate_modules


def check_new_module(files: list[str], repo: Path) -> dict | None:
    """检查 1: HEAD 不含的模块 + staged 未附合法 MODULE.md → block。

    F007: 只信 staged 证据
    F008: staged MODULE.md 必须通过 parse_module_md 校验（frontmatter 必填 + 枚举合法）
    """
    if _kill_switch():
        return None
    touched: dict[str, str | None] = {}  # module_name -> staged MODULE.md 路径 or None
    for p in files:
        mod = _module_name_from_path(p)
        if mod is None:
            continue
        touched.setdefault(mod, None)
        if p.replace("\\", "/").endswith(f"modules/{mod}/MODULE.md"):
            touched[mod] = p  # 记录 staged MODULE.md 相对路径
    blocking_missing: list[str] = []
    blocking_invalid: list[str] = []
    # F008: MODULE.md frontmatter 校验需要 aggregate 模块
    try:
        agg = _import_aggregate_module(repo)
    except Exception as e:
        # aggregate 脚本缺失本身是严重问题 —— block 而非静默
        if any(touched.get(m) for m in touched):
            return {
                "decision": "block",
                "reason": f"无法加载 aggregate_modules 校验 MODULE.md frontmatter: {e}",
            }
        agg = None
    for mod, md_rel in touched.items():
        if _dir_exists_in_head(repo, f"{MODULES_DIR}/{mod}"):
            continue  # 存量模块走 check_touched_legacy
        if md_rel is None:
            blocking_missing.append(mod)
            continue
        # F008: 校验 staged MODULE.md 内容合法
        if agg is not None:
            try:
                agg.parse_module_md(repo / md_rel)
            except Exception as e:
                blocking_invalid.append(f"{mod}: {e}")
    if blocking_missing or blocking_invalid:
        parts: list[str] = []
        if blocking_missing:
            parts.append(f"新建模块缺 MODULE.md (staged 未包含): {blocking_missing}。请按 docs/governance/MODULE-template.md 创建并 `git add`。")
        if blocking_invalid:
            parts.append("新建模块 MODULE.md frontmatter 非法:\n  - " + "\n  - ".join(blocking_invalid))
        return {"decision": "block", "reason": "\n".join(parts)}
    return None


def check_ownership_conflicts(modules: list[dict[str, Any]]) -> dict | None:
    if _kill_switch():
        return None
    table_owner: dict[str, str] = {}
    route_owner: dict[str, str] = {}
    conflicts: list[str] = []
    for m in modules:
        name = m.get("name", "?")
        for t in m.get("owns_tables") or []:
            prev = table_owner.get(t)
            if prev is not None and prev != name:
                conflicts.append(f"table '{t}': {prev} vs {name}")
            else:
                table_owner[t] = name
        for r in m.get("owns_routes") or []:
            prev = route_owner.get(r)
            if prev is not None and prev != name:
                conflicts.append(f"route '{r}': {prev} vs {name}")
            else:
                route_owner[r] = name
    if conflicts:
        return {
            "decision": "block",
            "reason": "owns_* 跨模块冲突（违反 L015 单一所有权）:\n  - " + "\n  - ".join(conflicts),
        }
    return None


def check_touched_legacy(files: list[str], diff: str, repo: Path) -> dict | None:
    """检查 2: 存量模块（HEAD 有）≥50 行改动缺 MODULE.md → ask。

    行数来自 parse_diff_line_counts(diff)。
    """
    if _kill_switch():
        return None
    line_counts = parse_diff_line_counts(diff)
    per_module: dict[str, int] = {}
    # 汇总每模块行数（files 与 diff 可能不完全重叠，以 files 为准，diff 补 count）
    for p in files:
        mod = _module_name_from_path(p)
        if mod is None:
            continue
        counts = line_counts.get(p, {"added": 0, "deleted": 0})
        per_module[mod] = per_module.get(mod, 0) + counts["added"] + counts["deleted"]
    asks: list[str] = []
    for mod, lines in per_module.items():
        if lines < LARGE_MODIFY_THRESHOLD:
            continue
        rel = f"{MODULES_DIR}/{mod}"
        if not _dir_exists_in_head(repo, rel):
            continue  # 新模块走 check_new_module
        # F007: 存量模块 MODULE.md 不存在时 ask；此处允许检查工作区（是否已写但未 staged），
        # 区别于 check_new_module 的严格策略——ask 是提示而非阻断，误差可容忍
        if not (repo / rel / "MODULE.md").exists():
            asks.append(f"{mod} ({lines} 行触碰)")
    if asks:
        return {
            "decision": "ask",
            "reason": (
                f"触碰存量模块 ≥{LARGE_MODIFY_THRESHOLD} 行但缺 MODULE.md:\n  - "
                + "\n  - ".join(asks)
                + "\n本次顺手补齐 MODULE.md？(Boy Scout 自愈式收敛)"
            ),
        }
    return None


class _LoaderError(RuntimeError):
    """F008: aggregate loader 失败必须向上抛，不得静默。"""


def _load_all_module_frontmatters(repo: Path) -> list[dict[str, Any]]:
    """读所有 MODULE.md frontmatter。任一失败 → raise _LoaderError（上层转 block）。"""
    modules_dir = repo / MODULES_DIR
    if not modules_dir.exists():
        return []
    # 先扫描是否有 MODULE.md；都没有就不需要 aggregate（自愈式早期阶段常态）
    md_files = [
        child / "MODULE.md"
        for child in sorted(modules_dir.iterdir())
        if child.is_dir() and not child.name.startswith("_") and child.name != "__pycache__"
        and (child / "MODULE.md").exists()
    ]
    if not md_files:
        return []
    try:
        agg = _import_aggregate_module(repo)
    except Exception as e:
        raise _LoaderError(f"aggregate_modules 不可导入: {e}") from e
    result: list[dict[str, Any]] = []
    for md in md_files:
        try:
            result.append(agg.parse_module_md(md))
        except Exception as e:
            raise _LoaderError(f"{md.relative_to(repo)}: {e}") from e
    return result


def check_derived_products_fresh(repo: Path, files: list[str]) -> dict | None:
    """检查 F009: 派生产物（modules.yaml / dependency-graph.md / debt-report.md）必须与 MODULE.md 同步。

    触发: staged 含任何 MODULE.md 或 modules/ 下代码变更。
    逻辑: 跑 aggregate_all → 对比 on-disk 派生产物 → 不一致 → block 并提示用户 `python scripts/governance/aggregate_modules.py && git add docs/governance/*`。
    参考模式: doc_sync_guard block-and-ask。
    """
    if _kill_switch():
        return None
    # 仅在 MODULE.md 或 modules/ 下有变更时触发（减少全量开销）
    trigger = any(
        p.replace("\\", "/").startswith(MODULES_DIR + "/")
        or p.replace("\\", "/").endswith("MODULE.md")
        for p in files
    )
    if not trigger:
        return None
    try:
        agg = _import_aggregate_module(repo)
    except Exception:
        return None  # 首次搭建阶段 aggregate 尚未存在 → 静默（Task 3 之前）
    out_dir = repo / "docs" / "governance"
    if not out_dir.exists():
        return None  # 设施未就绪
    import tempfile
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        try:
            agg.aggregate_all(repo / MODULES_DIR, tmp_path)
        except Exception:
            return None  # aggregate 错误由其他 check 捕获
        stale: list[str] = []
        for name in ("modules.yaml", "dependency-graph.md", "debt-report.md"):
            fresh = (tmp_path / name).read_text(encoding="utf-8") if (tmp_path / name).exists() else ""
            ondisk = (out_dir / name).read_text(encoding="utf-8") if (out_dir / name).exists() else ""
            if fresh != ondisk:
                stale.append(name)
        if stale:
            return {
                "decision": "block",
                "reason": (
                    f"派生产物过期 (违反设计 §3.1 单一真源): {stale}\n"
                    "请执行:\n"
                    "  python scripts/governance/aggregate_modules.py\n"
                    f"  git add docs/governance/{{{','.join(stale)}}}\n"
                    "然后重试 commit。"
                ),
            }
    return None


def check(data: dict, session_state, staged_info: dict | None = None) -> dict | None:
    """hook 入口（契约见模块 docstring）。"""
    if _kill_switch():
        return None
    cwd = data.get("cwd", ".")
    if not _is_edu_cloud(cwd):
        return None
    command = (data.get("tool_input") or {}).get("command", "")
    if "git commit" not in command:
        return None

    staged_info = staged_info or {}
    files: list[str] = [f for f in (staged_info.get("files") or []) if f]
    diff: str = staged_info.get("diff") or ""
    repo = Path(cwd)

    # F008: loader 失败必须 block 而非静默（无法校验冲突 = 治理失效）
    try:
        all_modules = _load_all_module_frontmatters(repo)
    except _LoaderError as e:
        return {
            "decision": "block",
            "reason": f"MODULE.md 解析失败，无法执行 owns 冲突检测: {e}",
        }

    for check_fn in (
        lambda: check_new_module(files, repo),
        lambda: check_ownership_conflicts(all_modules),
        lambda: check_derived_products_fresh(repo, files),
        lambda: check_touched_legacy(files, diff, repo),
    ):
        result = check_fn()
        if result is not None:
            return result
    return None
```

- [ ] **Step 4: Run tests to verify pass**

```bash
cd ~/edu-cloud && pytest tests/governance/test_module_governance_guard.py -v
```
Expected: 5 passed.

- [ ] **Step 5: Commit**

```bash
cd ~/.claude && git add hooks/module_governance_guard.py
cd ~/edu-cloud && git add tests/governance/test_module_governance_guard.py
cd ~/.claude && git commit -m "hook: module_governance_guard 核心实现（P3 Task 6）"
cd ~/edu-cloud && git commit -m "governance: P3-1 module_governance_guard 测试（5 tests）"
```

**测试契约:**
1. Diff 行数解析
   - 入口: `parse_diff_line_counts(diff)` → `{path: {added, deleted}}`
   - 反例: 错误实现可能把 `+++`/`---` 头行计入——test_parse_diff_line_counts_ignores_headers 捕获
   - 边界: 单文件 / 多文件 / 只加 / 只删
   - 回归: F006 防脱离真实 diff 结构
   - 命令: `pytest tests/governance/test_module_governance_guard.py::test_parse_diff_line_counts_basic tests/governance/test_module_governance_guard.py::test_parse_diff_line_counts_multi_file tests/governance/test_module_governance_guard.py::test_parse_diff_line_counts_ignores_headers -v`
2. 新模块判定（F002+F007）
   - 入口: `check_new_module(files, repo)` —— HEAD 不含 + staged 未附 MODULE.md
   - 反例 A: 错误实现可能用"MODULE.md 存在性"近似（F002）—— test_legacy_module_without_module_md_not_blocked_by_new_check 捕获
   - 反例 B: 错误实现可能接受"工作区存在但未 git add"（F007）—— test_new_module_module_md_in_workspace_but_not_staged_still_blocks 捕获
   - 边界: 新建无 MD / 新建有 MD staged / 新建 MD 只在工作区 / 存量缺 MD / 首次 commit（无 HEAD）
   - 回归: F002 防自愈式退化 + F007 防 git add 遗漏
   - 命令: `pytest tests/governance/test_module_governance_guard.py::test_new_module_without_module_md_blocks tests/governance/test_module_governance_guard.py::test_new_module_with_module_md_staged_passes tests/governance/test_module_governance_guard.py::test_new_module_module_md_in_workspace_but_not_staged_still_blocks tests/governance/test_module_governance_guard.py::test_legacy_module_without_module_md_not_blocked_by_new_check -v`
3. owns 冲突检测
   - 入口: `check_ownership_conflicts(modules)`
   - 反例: 错误实现可能自冲突误报——test_same_module_duplicate_owns_not_conflict 捕获
   - 边界: 空列表 / 同模块重复 / 跨模块冲突 / 多资源冲突
   - 回归: L015 单一所有权
   - 命令: `pytest tests/governance/test_module_governance_guard.py::test_duplicate_owns_tables_blocks tests/governance/test_module_governance_guard.py::test_same_module_duplicate_owns_not_conflict -v`
4. 存量触碰（files + diff 契约，F006）
   - 入口: `check_touched_legacy(files, diff, repo)`
   - 反例: 错误实现可能脱离 diff 直接期望预聚合 stats——当前实现从 diff 解析
   - 边界: ≥50 行 + 无 MD → ask / <50 行 → None / 行数刚好 49 vs 50
   - 回归: F006 真实 dispatcher 契约
   - 命令: `pytest tests/governance/test_module_governance_guard.py::test_large_modification_without_module_md_asks tests/governance/test_module_governance_guard.py::test_small_modification_does_not_ask -v`
5. Hook 入口级（F001+F004+F006）
   - 入口: `check(data, session_state, staged_info)` —— staged_info 真实结构 `{"files", "diff"}`
   - 反例: 错误实现可能单元 OK 但 hook wiring 返回结构错误——test_hook_entry_blocks_on_new_module_without_module_md 断言完整链路
   - 边界: edu-cloud repo / 非 edu-cloud repo / 非 git commit 命令 / 大 legacy 触碰
   - 回归: F001 防 no-op + F006 防契约错位
   - 命令: `pytest tests/governance/test_module_governance_guard.py::test_hook_entry_blocks_on_new_module_without_module_md tests/governance/test_module_governance_guard.py::test_hook_entry_asks_on_large_legacy_touch tests/governance/test_module_governance_guard.py::test_hook_entry_allows_non_edu_cloud_repo tests/governance/test_module_governance_guard.py::test_hook_entry_allows_non_git_commit_command -v`
6. **MODULE.md frontmatter 校验（F008）**
   - 入口: `check_new_module(files, repo)` 对 staged MODULE.md 调用 `aggregate_modules.parse_module_md`；`check()` 对存量非法 MODULE.md 由 loader raise `_LoaderError` 转 block
   - 反例: 错误实现可能仅检查文件存在而不校验内容——test_new_module_with_invalid_module_md_missing_field_blocks / test_new_module_with_invalid_yaml_blocks / test_check_entry_blocks_on_invalid_existing_module_md 捕获
   - 边界: 合法完整 / 缺字段 / YAML 错 / 存量非法
   - 回归: F008 防无效 MODULE.md 绕过治理
   - 命令: `pytest tests/governance/test_module_governance_guard.py::test_new_module_with_invalid_module_md_missing_field_blocks tests/governance/test_module_governance_guard.py::test_new_module_with_invalid_yaml_blocks tests/governance/test_module_governance_guard.py::test_check_entry_blocks_on_invalid_existing_module_md -v`
7. **派生产物同步检查（F009）**
   - 入口: `check_derived_products_fresh(repo, files)` 对比 `aggregate_all` 输出与 on-disk 产物
   - 反例: 错误实现可能漂移——test_derived_products_stale_blocks 断言 stale modules.yaml 会 block
   - 边界: 产物陈旧 / 产物新鲜 / docs/governance 不存在（首次搭建）
   - 回归: F009 防单一真源漂移
   - 命令: `pytest tests/governance/test_module_governance_guard.py::test_derived_products_stale_blocks tests/governance/test_module_governance_guard.py::test_derived_products_fresh_passes tests/governance/test_module_governance_guard.py::test_derived_products_check_skipped_when_no_governance_dir -v`
8. Kill switch 入口级
   - 入口: env `EDU_GOVERNANCE_GUARD_DISABLED=1` + check()
   - 反例: 错误实现可能部分 bypass —— test_kill_switch_disables_entry 从入口验证
   - 边界: 未设 / =1 / =0
   - 回归: 紧急回滚机制
   - 命令: `pytest tests/governance/test_module_governance_guard.py::test_kill_switch_disables_entry -v`

**边界条件:**
- 新建目录 + MODULE.md 已 staged → allow
- 新建目录 + MODULE.md 仅在工作区未 staged → **block（F007）**
- 存量目录 + <50 行 + 无 MODULE.md → allow（自愈式核心）
- 存量目录 + ≥50 行 + 无 MODULE.md → ask
- 非 edu-cloud repo → allow（不污染其他项目）
- EDU_GOVERNANCE_GUARD_DISABLED=1 → allow（所有层 bypass）

**审查清单:**
- ✓ `staged_info` 契约与 `~/.claude/hooks/commit_guards.py:99` 的 `{"files", "diff"}` 完全一致
- ✓ 行数统计来自 `parse_diff_line_counts(diff)` 而非 dispatcher 预聚合
- ✓ check() 签名 `(data, session_state, staged_info=None) -> dict | None`
- ✓ 返回 dict 而非自定义 dataclass
- ✓ 新模块 MODULE.md 合规只认 staged 证据（F007）
- ✓ 新旧判定用 `git ls-tree HEAD`（F002）
- ✓ **staged MODULE.md 必须通过 parse_module_md 校验（F008）**
- ✓ **存量 MODULE.md 解析失败 → loader raise _LoaderError → check() block（F008）**
- ✓ **派生产物过期 → check_derived_products_fresh block 并提示命令（F009）**
- ✓ KILL_SWITCH 在 check() 入口统一生效
- ✗ 禁止 hook 直接 sys.exit(1)
- ✗ 禁止用"MODULE.md 在工作区"兜底（F007 反退化）
- ✗ 禁止假设 staged_info 含 `paths` / `stats` 字段（F006 反退化）
- ✗ **禁止静默吞 parse/import 异常（F008 反退化）**
- ✗ **禁止只在手动流程更新派生产物（F009 反退化）**

---

### Task 7: 集成到 commit_guards.py（F001 修正）

**Files:**
- Modify: `~/.claude/hooks/commit_guards.py`

**F001 修正要点**：必须遵循 `commit_guards.py` 现有的 `CHECKS` 列表模式（见 `commit_guards.py:19-24`）。禁止引入 `run_all` / `additionalContext` 这类不存在的机制。

- [ ] **Step 1: 读 commit_guards.py 现有结构**

```bash
cat ~/.claude/hooks/commit_guards.py
```

关键事实（已确认）：
- `CHECKS = [("doc_sync_guard", doc_sync_guard.check), ("logging_guard", logging_guard.check), ("refactor_guard", refactor_guard.check)]`
- `run_checks(data, session_state, staged_info)` 遍历调用每个 `check(data, session_state, staged_info=None) -> dict | None`
- 优先级 `PRIORITY = {"block": 3, "ask": 2}`
- 结果 dict 使用 `decision` 字段；子 guard 返回 `None` 表示放行

- [ ] **Step 2: 在 CHECKS 列表追加 module_governance_guard**

Patch `~/.claude/hooks/commit_guards.py`：

```python
# 在现有 import 后追加：
import module_governance_guard

# CHECKS 列表追加一项：
CHECKS = [
    ("doc_sync_guard", doc_sync_guard.check),
    ("logging_guard", logging_guard.check),
    ("refactor_guard", refactor_guard.check),
    ("module_governance_guard", module_governance_guard.check),  # 新增
]
```

**不需要改 run_checks**——`module_governance_guard.check` 签名与其他一致，自带 edu-cloud cwd 过滤（见 Task 6 Step 3 的 `_is_edu_cloud`），其他仓库返回 None 不干扰。

- [ ] **Step 3: Hook 端到端行为验证（手动）**

场景 1：edu-cloud 新建 modules/testmod/ 无 MODULE.md
```bash
cd ~/edu-cloud
mkdir -p src/edu_cloud/modules/testmod
touch src/edu_cloud/modules/testmod/__init__.py
git add src/edu_cloud/modules/testmod/
git commit -m "test"
```
Expected: hook block，消息含 testmod。然后 `git reset HEAD -- . && rm -rf src/edu_cloud/modules/testmod` 回滚。

场景 2：设置 `EDU_GOVERNANCE_GUARD_DISABLED=1` 重复场景 1。
Expected: commit 通过。

场景 3：在其他仓库（如 `~/.claude`）commit。
Expected: 无新增检查项日志，原有三个 guard 正常工作。

记录每个场景的实际输出到 `docs/plans/.module-governance-hook-verify.log`（txt 追加）。

- [ ] **Step 4: Commit hook 改动**

```bash
cd ~/.claude
git add hooks/commit_guards.py hooks/module_governance_guard.py
git commit -m "sync(.claude): module_governance_guard 接入 commit_guards CHECKS（edu-cloud 专用）"
```

**审查清单:**
- ✓ `module_governance_guard.check` 签名与现有子 guard 完全一致
- ✓ CHECKS 列表追加而非重构调度函数
- ✓ 非 edu-cloud repo 返回 None（`_is_edu_cloud` 过滤）
- ✗ 禁止引入 `run_all` / `additionalContext` / 自定义聚合函数
- ✗ 禁止在 commit_guards.py 主文件写领域逻辑

---

### Task 8: Gate 2 PASS 后——设计收尾与文档回写（F005 修正）

**前置条件**：**必须**在 Gate 2 Code Review PASS 之后才能执行。Gate 2 未 PASS 时跳过本 Task。

**Files:**
- Modify: `~/.claude/CLAUDE.md`（安全铁律段）
- Modify: `~/edu-cloud/CLAUDE.md`（已完成设计段）
- Modify: `~/edu-cloud/docs/plans/2026-04-13-module-governance-design.md`（头部追加 [实现完成]）

- [ ] **Step 1: 确认 Gate 2 PASS 证据**

```bash
cat ~/edu-cloud/docs/plans/2026-04-13-module-governance-gates.json | python -c "import json,sys; d=json.load(sys.stdin); assert d['gates']['code_review']['status']=='pass', d; print('Gate 2 PASS confirmed')"
```
Expected: 输出 "Gate 2 PASS confirmed"；否则**终止本 Task**。

- [ ] **Step 2: 全局 CLAUDE.md 安全铁律追加**

Modify `~/.claude/CLAUDE.md` 「安全铁律」段末尾追加（一行）：

```markdown
- edu-cloud 模块治理：新建 modules/<X>/ 必须含 MODULE.md（module_governance_guard.py 拦截），owns_tables/owns_routes 跨模块重复硬阻断；KILL_SWITCH: EDU_GOVERNANCE_GUARD_DISABLED=1
```

- [ ] **Step 3: 项目 CLAUDE.md 已完成设计段追加**

Modify `~/edu-cloud/CLAUDE.md` 「已完成设计」段追加（N 和 commit 范围按实际数据填写）：

```markdown
- **edu-cloud 模块治理纲领 [实现完成]**: 四层治理模型（Layer 1 基线 + Layer 2 MODULE.md 契约 + Layer 3 modules.yaml 派生 + Layer 4 module_governance_guard.py）。P0 基线产出债务清单 {N} 条，用户拍板 approve/reject/defer；P2 试点 grading + pipeline MODULE.md 落地；P3 hook 接入 commit_guards.CHECKS，上线检查 1/3/4 (block) + 2 (ask)，检查 5/6 留待后续 phase。KILL_SWITCH: EDU_GOVERNANCE_GUARD_DISABLED。Gate 1 Plan Review Rx PASS；Gate 2 Code Review Rx PASS。→ `docs/plans/2026-04-13-module-governance-design.md`
```

- [ ] **Step 4: design.md 标记实现完成**

先运行 `date '+%Y-%m-%d %H:%M:%S'` 获取时间戳。

Modify `~/edu-cloud/docs/plans/2026-04-13-module-governance-design.md` 头部（§0 之后、§1 之前）追加：

```markdown
> [{YYYY-MM-DD HH:MM:SS} 实现完成] Commits: {first-sha}..{last-sha}
```

`{first-sha}` 为 Task 1 的第一个 commit；`{last-sha}` 为 Task 7 的 commit。

- [ ] **Step 5: Commit 收尾**

```bash
cd ~/.claude && git add CLAUDE.md
git commit -m "sync(.claude): 安全铁律追加 edu-cloud 模块治理条目"

cd ~/edu-cloud && git add CLAUDE.md docs/plans/2026-04-13-module-governance-design.md
git commit -m "design: 模块治理纲领 [实现完成] + 已完成设计回写"
```

**审查清单:**
- ✓ Step 1 的 gates.json 校验必须先执行，确认 code_review.status == pass
- ✓ `{N}` / `{Rx}` / `{first-sha}` / `{last-sha}` 必须用真实数据替换（无 placeholder 留存）
- ✓ design.md 的 `[实现完成]` 标记位置在 §0 之后（与项目惯例一致）
- ✗ 禁止在 Gate 2 未 PASS 时执行本 Task（F005 核心约束）

**边界条件:**
- Gate 2 R1 FAIL → R2 PASS：本 Task 在 R2 后执行，`{Rx}` 写 R2
- Gate 2 三轮后仍未 PASS：本 Task 不执行，进入 FAIL 升级处置（设计待处置段）
- gates.json 文件损坏/缺失：Step 1 命令失败 → 终止本 Task 并报告用户

---

## Phase Gates（T3 流程强制）

**Gate 1 — Plan Review（本 plan 完成后，进入执行前）**:
- 新会话由 codex-review skill 对 design + plan 做审查
- finding 处置完成并 commit final plan 后，才能开工

**Gate 2 — Code Review（单批次 P0+P1+P2+P3 全量审）**:
- 本 T3 按 1 批次设计，所有 Task 完成后一次性送审
- codex-review (code) 审整个实现，FAIL 则修复重审（最多 3 轮）

**Gate 关闭**:
- Task 8（仅在 Gate 2 PASS 后执行）的 CLAUDE.md 回写 + design.md `[实现完成]` 标记构成 Gate 关闭证据
- Task 8 Step 1 的 gates.json 校验是执行前置，违反 L015 纪律（"[实现完成]" 反映当前真实状态）会被该校验拦截

---

## Self-Review（plan 作者自审 + R2/R3/R4 修复记录）

**R4 修复（基于 Gate 1 R3 FAIL 的 2 findings）**:
- **F008** HIGH RESOLVED: `check_new_module` 对 staged MODULE.md 调用 `parse_module_md()` 校验 frontmatter；`_load_all_module_frontmatters` 抛 `_LoaderError`（不再吞异常）；`check()` 捕获 loader 错误转 block；新增 4 条反退化测试（missing field / invalid YAML / staged 非法 / 存量非法）
- **F009** MED RESOLVED: 新增 `check_derived_products_fresh(repo, files)` hook 检查——触发条件：staged 含 modules/ 或 MODULE.md 变更；逻辑：tempdir 跑 aggregate_all → 对比 on-disk 派生产物 → 不一致 block 并给出补救命令；新增 3 条测试（陈旧 block / 新鲜 pass / 首次搭建跳过）
- **覆盖率核查（R4 前置）**: 对照 design.md 逐项映射 plan Task——F008/F009 是 design §2 字段校验矩阵 + §3.1 auto-stage 承诺未兑现的两处缺口。今后 R0 应先做 design→plan 承诺清单，避免每轮被动发现

**R3 修复（基于 Gate 1 R2 FAIL 的 3 findings）**:
- **F003 残留** HIGH RESOLVED: Task 5 Step 3 Expected 改为"依赖图反映真实读到的模块依赖，方向由代码决定"，不再硬编码 grading→pipeline
- **F006** HIGH 新 RESOLVED: `staged_info` 契约对齐实读 commit_guards.py:99 的 `{"files", "diff"}`；新增 `parse_diff_line_counts(diff)` 从 diff 解析每文件增删行数；`check_touched_legacy` 签名改为 `(files, diff, repo)`
- **F007** HIGH 新 RESOLVED: `check_new_module` 删除工作区兜底（`(repo / rel / "MODULE.md").exists()`），只信 staged files 证据；新增 `test_new_module_module_md_in_workspace_but_not_staged_still_blocks` 反退化测试
- **方法论教训（feedback_research_over_rules）**: R1 修复时自称"严格对齐 commit_guards.check 签名"但未完整读 commit_guards.py 的 main() 函数，只看了 CHECKS 列表结构——导致 staged_info 契约凭空编造。R2 修复前必须先执行 `sed -n '60,120p' ~/.claude/hooks/commit_guards.py` 获取真实构造代码再写 plan。

**R2 修复（基于 Gate 1 R1 FAIL 的 5 findings）**:
- **F001** HIGH code-bug RESOLVED: Task 6 Step 3 重写为 `check(data, session_state, staged_info) -> dict | None` 严格对齐 commit_guards 子 guard 契约；Task 7 Step 2 改用 CHECKS 列表追加模式，删除虚构的 `run_all` / `additionalContext`
- **F002** HIGH code-bug RESOLVED: `check_new_module` 改用 `git ls-tree HEAD` evidence 判定新旧；新增 `test_legacy_module_touched_without_module_md_does_NOT_block` 作为反退化测试
- **F003** HIGH code-bug RESOLVED: Task 4/5 Step 2 删除对 grading/pipeline 职责分工的预设叙述，改为"Executor 读代码实情填写"；Task 5 补充冲突检测前提（真冲突记入 baseline 暂停，不捏造归属）
- **F004** MED test-gap RESOLVED: Task 3 新增 CLI 入口测试（subprocess 跑 aggregate_modules.py）；Task 6 新增 hook 入口级测试（完整 check() 调用 + 模拟 payload）
- **F005** MED design-concern RESOLVED: 拆出新 Task 8，将 CLAUDE.md 回写 + `[实现完成]` 标记移到 Gate 2 PASS 之后；Task 8 Step 1 用 gates.json 机械校验前置条件

**1. Spec coverage**:
- design §1 四层架构 → Task 1 (Layer 1) / Task 2-3 (Layer 2+3) / Task 4-5 (Layer 2 试点) / Task 6-7 (Layer 4)
- design §2 MODULE.md 模板 → Task 2
- design §3.1 聚合脚本 → Task 3
- design §3.2 六条守卫 → Task 6（1/2/3/4 + kill switch；5/6 渐进延后，设计 §4 明注）
- design §3.3 调研方法论 → Task 1
- design §4 实施路线 P0-P3 → Phase P0-P3
- design §6 交付物清单 → Task 1-8 的 Files 段全覆盖
- **Gap**: 检查 5、6 按 design §4 "P3 渐进开启" 延后——非遗漏。

**2. Placeholder scan**:
- Task 8 Step 3 `{N}` / `{Rx}` / `{first-sha}` / `{last-sha}` 是占位，审查清单第 2 项强制"真实数据替换"——接受为执行时填空。
- 无其他 TBD / TODO。

**3. Type consistency**:
- `check(data, session_state, staged_info) -> dict | None` 在 Task 6 Step 3 和 Task 7 Step 2 中完全一致
- `ModuleGovernanceError` 仅在 Task 3 定义使用；`check_new_module` / `check_ownership_conflicts` / `check_touched_legacy` 在 Task 6 测试和实现中签名一致
- `_is_edu_cloud` / `_dir_exists_in_head` 为 Task 6 内部辅助，不跨 Task 引用

**3. Type consistency**:
- `ModuleGovernanceError` / `Decision` / `parse_module_md` / `aggregate_all` / `detect_conflicts` 在 Task 3 和 Task 6 引用一致
- `_module_name_from_path` 内部辅助，命名一致
- 检查 5/6 未实现不影响类型一致性

**无需修改。**

---

## 执行 Handoff

**新会话执行（T3 铁律）**：
```
[edu-cloud] Executor | {YYYY-MM-DD HH:MM:SS}
项目: C:\Users\Administrator\edu-cloud
读取 docs/plans/2026-04-13-module-governance-design.md 与 docs/plans/2026-04-13-module-governance-plan.md。
按 Task 1→7 顺序执行（Task 8 为 Gate 2 PASS 后收尾，暂不执行），使用 executing-plans skill。
Gate 1 已在本 plan 提交后由 codex-review (plan) 完成（R2 PASS）。
Task 1-7 完成后输出审查交接单，调用 codex-review (code) 做 Gate 2。
Gate 2 PASS 后再执行 Task 8（CLAUDE.md 回写 + design.md 实现完成标记）。
```

**选项**：
1. **Inline Execution（推荐此 T3）** — 新会话使用 executing-plans，单批次 7 Task 全量交付，末端审查交接单 + codex-review Gate 2
2. Subagent-Driven — 本 plan 不适用（T3 + 需要 Opus 亲自做 P0 调研，不能委派）

用户本次会话结束后另开新会话，贴上面的执行指令即可启动。
