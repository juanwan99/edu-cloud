# 模块化架构接入 · Plan 1：恢复 WIP + 前置清理 + 边界 gate 前置

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.
> **设计来源**：`docs/plans/2026-05-29-modular-arch-integration-design.md`（§4 前置清理 + 阶段0；已吸收 GPT 评审 7 finding）。
> **本 Plan 范围**：渐进分层的**第一砖（准备层）**——把 stash 架构代码恢复进隔离 worktree、清理误导测试、立起边界冻结闸门。**不碰 `app.py`/`auth.py` 生产启动路径**（阶段1 接入是 Plan 2）。

**Goal:** 将 stash@{0}（object `38fab1d`）的 P0–P6 架构 WIP 恢复进独立 git worktree，完成零风险前置清理（F-005/F-006/F-007），并在动任何生产代码前立起模块边界 baseline gate。

**Architecture:** 隔离 worktree 作业（不污染主工作树）；恢复后立即 commit 固化（不再依赖可变 stash）；前置清理只改测试/文档，不改生产启动路径；边界 gate 用"冻结当前 139 违规为 baseline + negative-delta 检查"，先于阶段1–4 任何代码改动就位。

**Tech Stack:** Python 3.14 + pytest + 异步 SQLAlchemy；git worktree + git stash；`scripts/audit_boundaries.py`（AST 跨模块导入审计）。

**Tier:** T3（架构接入起点；但本 Plan 自身不动生产路径，风险集中在"恢复正确性"与"基线真实性"）。

---

## 前置事实（执行前必读）

- **恢复对象**：`git stash list` 中 msg "WIP: 模块化架构 P0-P6..." 的不可变 object = `38fab1d548cc026ad81fea1aae172727398e383a`。**用 object 不用 `stash@{0}` 别名**（别名会漂移，GPT F-07）。
- **stash 内容**：32 文件 / +4369 行（tracked 改动 3 个：`CLAUDE.md`、`triggers.py`、删 `events.py`；其余 29 个 untracked 新文件——见 design §2.2）。
- **当前基线**：主分支 `codex/role-permission-phase2`，HEAD `d01d217`（= `40610c2` + 本 Plan doc commit），工作树 clean，backend 运行 `b763888`。worktree 基于 `d01d217` 新建分支 `modular-arch-restore`。
- **F-006 已在 stash 内修复**：`triggers.py` stash 版已用 `from edu_cloud.core.events import LegacyEventBus`（工作树版仍是旧 `EventBus`）。恢复即得，**本 Plan 不再单独改 triggers.py**，仅验证。

---

## Task 1：创建隔离 worktree 并恢复架构 WIP

**Files:**
- 无文件编辑（git 操作）

- [ ] **Step 1: 创建隔离 worktree（用 using-git-worktrees skill 或原生命令）**

Run:
```bash
cd /home/ops/projects/edu-cloud
# 主工作树已 checkout codex/role-permission-phase2，git 拒绝同分支双 checkout → 必须用新分支隔离
# 基点用 HEAD（codex/role-permission-phase2 当前 tip，含全部 plan 修正；GPT R-001：不回退到旧祖先 commit）
git worktree add -b modular-arch-restore ../edu-cloud-modular-arch HEAD
cd ../edu-cloud-modular-arch
# 复用主仓 .venv（Plan 1 无依赖文件变更 → symlink，等价 subagent-worktree-bootstrap 的无变更分支）
ln -sfn /home/ops/projects/edu-cloud/.venv .venv
.venv/bin/python --version  # 验证 symlink 生效（应为 Python 3.14.x）
```
Expected: 新 worktree 在 `../edu-cloud-modular-arch`，分支 `modular-arch-restore`，HEAD = 主仓当前 tip（含全部 plan 修正，`git -C ../edu-cloud-modular-arch rev-parse --short HEAD` 应等于主仓 `git rev-parse --short HEAD`），工作树 clean；`.venv` symlink 指向主仓且 `python --version` 正常。

- [ ] **Step 2: 在 worktree 中恢复 stash（用 apply 不用 pop，保留 stash 不丢）**

Run:
```bash
git stash apply 38fab1d
git status --short | wc -l
```
Expected: 恢复后 `git status` 显示 32 个文件变更（含 untracked 新文件）；`git stash list` 仍含原 stash（apply 不删）。

- [ ] **Step 3: 验证关键架构文件已落地**

Run:
```bash
ls src/edu_cloud/core/modules/loader.py \
   src/edu_cloud/core/permission_compiler/roles.yaml \
   src/edu_cloud/core/secure_router.py \
   scripts/audit_boundaries.py
git show :src/edu_cloud/ai/workflow/triggers.py 2>/dev/null | grep -c LegacyEventBus || grep -c LegacyEventBus src/edu_cloud/ai/workflow/triggers.py
```
Expected: 四个文件都存在；`triggers.py` 含 `LegacyEventBus`（F-006 已修，确认）。

- [ ] **Step 4: 立即 commit 固化恢复态（不再依赖可变 stash，GPT F-07）**

Run:
```bash
git add -A
git commit -m "restore: 恢复模块化架构 P0-P6 WIP 到 worktree（base stash 38fab1d）"
git rev-parse --short HEAD
```
Expected: 新 commit 记录恢复态 head；后续工作锚定此 commit。

---

## Task 2：记录恢复态全量测试基线

**Files:**
- Create: `docs/plans/.modular-arch-restore-baseline.txt`（全量输出快照，git 跟踪）
- Create: `docs/plans/.modular-arch-restore-failed.txt`（failed/error nodeid 全集，ORC-2 机械对比依据，git 跟踪）

- [ ] **Step 1: 跑全量后端测试，完整落盘基线（R-005：不得用 tail 截断 failed 集合）**

Run:
```bash
# -rfE 打印 failed+error 的 short summary（含每个 nodeid）；tee 落完整输出（不截断），tail 仅供屏幕摘要
.venv/bin/python -m pytest --tb=no -q -rfE 2>&1 | tee docs/plans/.modular-arch-restore-baseline.txt | tail -25
# 抽取 failed/error nodeid 全集并排序（ORC-2 单调对比的机械依据，不受 tail 窗口影响）
grep -E "^(FAILED|ERROR) " docs/plans/.modular-arch-restore-baseline.txt | sort > docs/plans/.modular-arch-restore-failed.txt
echo "failed/error 总数: $(wc -l < docs/plans/.modular-arch-restore-failed.txt)"
```
Expected: `.modular-arch-restore-baseline.txt` 含完整 pytest 输出（含 summary 段每个 FAILED/ERROR nodeid，无 tail 截断）；`.modular-arch-restore-failed.txt` 为排序后的 failed/error nodeid 全集。这是"恢复态基线"，后续阶段 failed 集合须 ⊆ 此集合 ∪ {新增 xfail}（ORC-2）。

- [ ] **Step 2: 标注基线中每个 failed 的归属**

在 `docs/plans/.modular-arch-restore-baseline.txt` 末尾追加每个 failing test 的一行归类：`新架构未接入引入 / 存量已知失败 / 需调查`。参照 design §2.2 与 memory（恢复前 clean 基线为"6 个非生产失败"）。

- [ ] **Step 3: Commit 基线**

Run:
```bash
git add docs/plans/.modular-arch-restore-baseline.txt docs/plans/.modular-arch-restore-failed.txt
git commit -m "test: 记录模块化架构恢复态测试基线（含 failed nodeid 全集）"
```

---

## Task 3：前置清理 F-006 验证 + F-007 plan 元数据

**Files:**
- Verify: `src/edu_cloud/ai/workflow/triggers.py`（仅验证，stash 已修）
- Modify: `docs/plans/2026-05-29-modular-architecture-p0-p6-plan.md`（F-007 元数据笔误）

- [ ] **Step 1: 验证 F-006（triggers 注解已是 LegacyEventBus）**

Run:
```bash
grep -n "EventBus" src/edu_cloud/ai/workflow/triggers.py
```
Expected: 所有 `EventBus` 引用均为 `LegacyEventBus`（import 与类型注解一致）。若仍有裸 `EventBus` → 改为 `LegacyEventBus`。

- [ ] **Step 2: 修 F-007 plan 元数据（文件数 31→实际、HEAD 漂移说明）**

读取 `docs/plans/2026-05-29-modular-architecture-p0-p6-plan.md` 的"实现状态"段，把"32 文件 / HEAD e7e5ddf"更正为"32 文件变更（含 calendar/manifest 等），HEAD 已随后续 commit 漂移，以恢复 commit 为准"。

- [ ] **Step 3: Commit**

Run:
```bash
git add -A
git commit -m "docs: 修 F-007 plan 元数据 + 确认 F-006 triggers 注解"
```

---

## Task 4：前置清理 F-005 — 误导测试摘为独立 xfail

**Files:**
- Modify: `tests/test_base_service.py`（`test_list_tenant_isolation` 约 :138–:152）

> **背景**：`test_base_service.py:152` `assert page_all.total == 8` 把"漏传 school_id 返回 8 条跨租户全部"记成现状（已带 FIXME 注释）。fail-closed 实现在**阶段3（Plan 3）**，故本 Plan **不改实现**，只把这个不安全断言摘成独立测试并标 `xfail(strict=True)`——消除"跨租户返回是对的"的误导，又不引入红测试。阶段3 实现 fail-closed 后该 xfail 会 xpass，strict 模式强制提醒去掉标记并转正。

- [ ] **Step 1: 先读真实结构确认行号**

Run:
```bash
sed -n '136,156p' tests/test_base_service.py
```
Expected: 看到 `test_list_tenant_isolation` 中 seed school-a(3)+school-b(5)，`page_all = await svc.list(db)`（漏传 school_id），`assert page_all.total == 8` 带 FIXME。

- [ ] **Step 2: 改造——把漏传断言摘成独立 xfail 测试**

在 `test_list_tenant_isolation` 中**删除**漏传 school_id 的 `page_all` 段（保留 school-a==3 / school-b==5 的正常租户隔离断言），并新增独立测试：

```python
@pytest.mark.xfail(
    strict=True,
    reason="F-005: BaseService fail-closed 实现在 Plan 3（阶段3）；"
           "漏传 school_id 应拒绝/返回空，当前不安全返回跨租户全部。"
           "实现后此用例 xpass，strict 模式会强制转正。",
)
async def test_list_missing_tenant_context_is_fail_closed(db, svc):
    """漏传 school_id（缺失租户上下文）必须 fail-closed：不得返回跨租户数据。

    反例：错误实现会 `return all 8 rows`（旧不安全行为）→ 本断言 total==0 失败暴露之。
    边界：受限角色无 school_id（缺失上下文）≠ 授权全量角色（None=合法全校）——
    后者由 Plan 3 的 UNRESTRICTED/MISSING 状态机区分，本用例仅锁缺失上下文一态。
    """
    await _seed_items(db, 3, school_id="school-a")
    await _seed_items(db, 5, school_id="school-b")
    page_all = await svc.list(db)  # 漏传 school_id = 缺失租户上下文
    assert page_all.total == 0  # fail-closed：缺失上下文不返回任何跨租户行
```

- [ ] **Step 3: 运行确认为 xfail（非 pass、非 error）**

Run:
```bash
.venv/bin/python -m pytest tests/test_base_service.py -q 2>&1 | tail -8
```
Expected: `test_list_missing_tenant_context_is_fail_closed` 计为 **xfailed**（当前实现非 fail-closed，断言 total==0 失败 → 符合 xfail 预期）；`test_list_tenant_isolation` 仍 pass；无新增 error。

- [ ] **Step 4: Commit**

Run:
```bash
git add tests/test_base_service.py
git commit -m "test: F-005 误导断言摘为独立 xfail（fail-closed 期望，实现待 Plan 3）"
```

---

## Task 5：边界 baseline gate 前置

**Files:**
- Modify: `scripts/audit_boundaries.py`（`main()` 增 `--check`/`--write-baseline`/`--baseline`，gate 按"违规身份(edge)+总数"双判定）
- Create: `docs/plans/.boundary-baseline.json`（冻结基线：total + 排序 edge 集，git 跟踪）
- Test: `tests/test_audit_boundaries_gate.py`

> **背景**：`audit_boundaries.py` 当前 `main()` 永远 `sys.exit(0)`（仅报告）。本 Task 加 baseline 冻结 + **edge-identity hybrid negative-delta gate**：`--write-baseline` 冻结当前违规总数**与跨模块 edge 集**；`--check` 在「出现 baseline 外的新 edge」**或**「total 上升」时 `exit(1)`；audit 自身出错时 gate 模式 `exit(2)`（**不绿灯**，GPT R-002）。**先于阶段1–4 就位**（design §4 阶段0）。存量 139 的消除仍属阶段4。
> **为何按 edge 身份而非纯总数**（GPT R-003 design_concern / design §68「新增违规即失败」、§133「新增跨界违规被拦截」）：纯比总数可被"删 1 旧 + 增 1 新、总数持平"绕过。按 `(source_module → target_module)` edge 集做 negative-delta（`audit()` 已含该字段，见 stash 版 `:157` `viol_edges`），删旧增新会因出现新 edge 被拦；叠加总数检查，旧 edge 上新增 import（total 升）也被拦。两者取并集，严格强于任一单独判定。

- [ ] **Step 1: 跑现状，确认违规总数与 edge 集（baseline 真值）**

Run:
```bash
.venv/bin/python scripts/audit_boundaries.py --json 2>&1 | grep -E "violation_count|total_violations"
```
Expected: 输出 `violation_count`（design 记 139；以**实测为准**，恢复态可能微调）。记下该数 N。edge 集由实现从 `result["violations"]` 的 `(source_module, target_module)` 派生。

- [ ] **Step 2: 写失败测试（gate 行为，覆盖 edge/总数/缺失/写基线/错误 五类 — GPT R-004）**

> **先读真实结构**：`sed -n '64,100p;167,190p' scripts/audit_boundaries.py` 确认 `audit()` 返回 `violations`（每条含 `source_module`/`target_module`）、`--json` 输出 `violation_count`、`main()` 在 `if __name__=="__main__"` guard 下（测试可安全 import）。

Create `tests/test_audit_boundaries_gate.py`：
```python
import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
SCRIPT = REPO / "scripts" / "audit_boundaries.py"


def _run(*args):
    return subprocess.run(
        [sys.executable, str(SCRIPT), *args],
        capture_output=True, text=True, cwd=REPO,
    )


def _load_module():
    spec = importlib.util.spec_from_file_location("audit_boundaries_under_test", SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)  # __main__ guard 存在，import 不触发 main()
    return mod


def _current(mod):
    r = mod.audit()
    edges = sorted({f"{v['source_module']} -> {v['target_module']}" for v in r["violations"]})
    return r["total_violations"], edges


def test_check_passes_at_baseline(tmp_path):
    """当前违规 == baseline（同 total、edges 全覆盖）→ exit 0。"""
    mod = _load_module()
    total, edges = _current(mod)
    bf = tmp_path / "baseline.json"
    bf.write_text(json.dumps({"total_violations": total, "edges": edges}))
    r = _run("--check", "--baseline", str(bf))
    assert r.returncode == 0, f"baseline 内不应失败: rc={r.returncode} {r.stderr}"


def test_check_fails_on_new_edge(tmp_path):
    """R-003 核心：total 不超标但出现 baseline 外的新 edge → exit 1。"""
    mod = _load_module()
    total, _edges = _current(mod)
    bf = tmp_path / "baseline.json"
    bf.write_text(json.dumps({"total_violations": total + 9999, "edges": []}))
    r = _run("--check", "--baseline", str(bf))
    assert r.returncode == 1, f"出现新 edge 必须 exit 1: rc={r.returncode}"
    assert "BOUNDARY GATE FAIL" in r.stderr


def test_check_fails_on_count_increase(tmp_path):
    """旧 edge 上新增 import（total 升、无新 edge）→ exit 1。edges 全覆盖 + total=-1 模拟。"""
    mod = _load_module()
    total, edges = _current(mod)
    bf = tmp_path / "baseline.json"
    bf.write_text(json.dumps({"total_violations": -1, "edges": edges}))
    r = _run("--check", "--baseline", str(bf))
    assert r.returncode == 1, f"total 超标必须 exit 1: rc={r.returncode}"
    assert "BOUNDARY GATE FAIL" in r.stderr


def test_check_missing_baseline_exit2():
    """baseline 文件缺失 → exit 2（非 0，不静默放行）。"""
    r = _run("--check", "--baseline", "/nonexistent/baseline.json")
    assert r.returncode == 2, f"baseline 缺失须 exit 2: rc={r.returncode}"


def test_write_baseline_content(tmp_path):
    """--write-baseline 落盘 total(int) + edges(排序 list)，且 total == --json violation_count。"""
    bf = tmp_path / "baseline.json"
    r = _run("--write-baseline", "--baseline", str(bf))
    assert r.returncode == 0, r.stderr
    data = json.loads(bf.read_text())
    assert isinstance(data["total_violations"], int)
    assert isinstance(data["edges"], list) and data["edges"] == sorted(data["edges"])
    jdata = json.loads(_run("--json").stdout)
    assert data["total_violations"] == jdata["violation_count"]


def test_gate_mode_audit_error_exits_nonzero(monkeypatch):
    """R-002：gate 模式下 audit 内部错误必须非零退出（不得 exit 0 绿灯）。"""
    mod = _load_module()
    monkeypatch.setattr(mod, "audit", lambda: {"error": "simulated audit failure"})
    monkeypatch.setattr(sys, "argv", ["audit_boundaries.py", "--check"])
    with pytest.raises(SystemExit) as ei:
        mod.main()
    assert ei.value.code not in (0, None), f"gate 模式 audit 错误必须非零退出, got {ei.value.code}"
```

- [ ] **Step 3: 运行测试确认失败**

Run:
```bash
.venv/bin/python -m pytest tests/test_audit_boundaries_gate.py -q
```
Expected: FAIL（`--check`/`--baseline`/`--write-baseline` 尚未实现）。

- [ ] **Step 4: 实现 gate（改 `audit_boundaries.py` main）— edge-identity hybrid + 错误非零退出**

在 `main()` argparse 增参数；**先处理 audit 错误（gate 模式非零退出，R-002）**，再分支 write-baseline / check（默认报告分支保持 `exit(0)` 向后兼容）：
```python
    ap.add_argument("--check", action="store_true",
                    help="Gate mode: exit 1 if new edges appear or total increases vs baseline")
    ap.add_argument("--write-baseline", action="store_true",
                    help="Freeze current violations (total + edge set) as baseline")
    ap.add_argument("--baseline", default="docs/plans/.boundary-baseline.json",
                    help="Baseline file path")
    args = ap.parse_args()
    result = audit()

    gate_mode = args.check or args.write_baseline
    if "error" in result:
        print(result["error"], file=sys.stderr)
        sys.exit(2 if gate_mode else 0)   # R-002: gate 模式不绿灯

    def _edges(res):
        return sorted({f"{v['source_module']} -> {v['target_module']}"
                       for v in res["violations"]})

    if args.write_baseline:
        import json as _json
        from pathlib import Path as _Path
        payload = {"total_violations": result["total_violations"], "edges": _edges(result)}
        _Path(args.baseline).write_text(
            _json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
        print(f"Baseline frozen: {payload['total_violations']} violations / "
              f"{len(payload['edges'])} edges -> {args.baseline}")
        sys.exit(0)

    if args.check:
        import json as _json
        from pathlib import Path as _Path
        bf = _Path(args.baseline)
        if not bf.exists():
            print(f"Baseline missing: {args.baseline} (run --write-baseline)", file=sys.stderr)
            sys.exit(2)
        base = _json.loads(bf.read_text(encoding="utf-8"))
        base_total = base["total_violations"]
        base_edges = set(base.get("edges", []))
        cur_total = result["total_violations"]
        new_edges = sorted(set(_edges(result)) - base_edges)
        if new_edges or cur_total > base_total:
            print(f"BOUNDARY GATE FAIL: total {cur_total} vs baseline {base_total}; "
                  f"new edges ({len(new_edges)}): {new_edges}", file=sys.stderr)
            sys.exit(1)
        print(f"Boundary gate OK: total {cur_total} <= {base_total}, no new edges")
        sys.exit(0)
```
（其余 `--json`/`--graph`/默认报告分支保持不变。）

- [ ] **Step 5: 冻结 baseline**

Run:
```bash
.venv/bin/python scripts/audit_boundaries.py --write-baseline
cat docs/plans/.boundary-baseline.json
```
Expected: 生成 `{"total_violations": N, "edges": [...]}`（N = Step 1 实测值，edges 排序后的跨模块 edge 集）。

- [ ] **Step 6: 运行测试确认通过**

Run:
```bash
.venv/bin/python -m pytest tests/test_audit_boundaries_gate.py -q
```
Expected: PASS（6 用例：baseline 内通过 / 新 edge 失败 / total 升失败 / baseline 缺失 exit2 / 写基线内容正确 / audit 错误非零退出）。

- [ ] **Step 7: Commit**

Run:
```bash
git add scripts/audit_boundaries.py tests/test_audit_boundaries_gate.py docs/plans/.boundary-baseline.json
git commit -m "feat: 边界 baseline gate 前置 — 冻结 139(total+edge集) + edge-identity hybrid negative-delta + 错误非零退出（design 阶段0/F-04; GPT R-002/R-003/R-004）"
```

---

## semantic_regression（ORC 不变量，codex-review 提取）

- **ORC-1（恢复完整性）**：`git stash apply 38fab1d` 后工作树恰好新增/修改 32 文件；`git stash list` 仍含原 object（apply 未 drop）。验证：`git stash show --include-untracked --stat 38fab1d | tail -1` 显示 `32 files`。
- **ORC-2（基线单调）**：恢复态测试基线完整落盘 `docs/plans/.modular-arch-restore-baseline.txt`，failed/error nodeid 全集落盘 `docs/plans/.modular-arch-restore-failed.txt`（不受 tail 截断，GPT R-005）；本 Plan 结束时 failed 集合 ⊆ 基线 failed ∪ {新增 xfail}，无新真实回归。验证：对比 Plan 前后 `.modular-arch-restore-failed.txt` 与实测 failed 清单。
- **ORC-3（F-005 不被静默）**：`test_list_missing_tenant_context_is_fail_closed` 在 CI 中为 **xfailed**（非 pass、非 skip、非 deselect）；实现 fail-closed 后会 xpass 并因 `strict=True` 失败提醒转正。验证：`pytest -rxX tests/test_base_service.py` 显示该用例 XFAIL。
- **ORC-4（边界 gate 真实）**：`.boundary-baseline.json` 的 `total_violations` == `audit_boundaries.py --json` 的 `violation_count`，且 `edges` 为排序后跨模块 edge 全集；`--check` 对「新 edge 出现」**或**「total 上升」返回 exit 1，对 audit 内部错误返回 exit 2（gate 模式不绿灯，GPT R-002）。验证：Task 5 Step 6 六用例全 PASS。
- **ORC-5（不碰生产路径）**：本 Plan 全程不修改 `src/edu_cloud/api/app.py`、`src/edu_cloud/core/auth.py`。验证：`git diff <Plan起点>..HEAD --name-only | grep -E "api/app.py|core/auth.py"` 应为空。

---

## Self-Review（写完即查）

- **Spec 覆盖**：覆盖 design §4「前置清理」(F-005/F-006/F-007) + 「阶段0」(恢复 + 边界 gate 前置)。阶段1–4 不在本 Plan（后续 Plan 2–5），已显式声明。✅
- **Placeholder 扫描**：无 TBD/TODO；每个代码步骤含完整代码；Task 4 Step 1 / Task 5 Step 1 先读真实文件再改，是核对非占位。✅
- **类型一致**：`--baseline` 参数名在 main 实现、测试、`--write-baseline`/`--check` 三处一致；baseline 文件路径 `docs/plans/.boundary-baseline.json` 全文统一。✅
- **风险**：Task 1 worktree 依赖主仓 .venv（依赖隔离策略：symlink 复用）；若 stash apply 冲突（HEAD 已从 stash base 漂移）→ 退回逐文件 `git checkout 38fab1d^3 -- <path>` 取 untracked + `git stash show -p` 打 tracked patch。

---

## GPT Plan Review R1 处置（FAIL → 修订，原始 log `docs/plans/.codex-plan1-review-raw.log`）

| Finding | 级别 | Type | 处置 |
|---------|------|------|------|
| R-001 | MED | defect_fix | Task 1 worktree 基点 `d01d217` → `HEAD`（含全部 plan 修正），Expected 改为校验与主仓 tip 一致 |
| R-002 | HIGH | defect_fix | Task 5 Step 4：audit 出错时 gate 模式 `exit(2)` 不绿灯（默认报告模式仍 `exit(0)` 兼容）；新增 `test_gate_mode_audit_error_exits_nonzero` |
| R-003 | MED | design_concern | 架构裁决：gate 升级为 **edge-identity hybrid**（新 edge 或 total 上升即 fail），忠于 design §68/§133「新增违规即失败」；新增 `test_check_fails_on_new_edge` |
| R-004 | MED | test_gap | Task 5 测试扩为 6 用例：覆盖 `--write-baseline` 内容/`--baseline`/缺失 exit2/失败 stderr `BOUNDARY GATE FAIL`/错误退出 |
| R-005 | MED | test_gap | Task 2：完整 `tee` 落盘 + 抽取排序 failed/error nodeid 全集到 `.modular-arch-restore-failed.txt`（不被 tail 截断），ORC-2 可机械对比 |

预审修正（commit `5921a49`，先于 R1）：文件名合 `-plan.md` 约定（解锁 receipt 绑定）、worktree 新分支（避免同分支双 checkout）、补 .venv symlink。
