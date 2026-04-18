<!-- legacy-format -->
# T-E Takeover 影响面全景 Audit Report · 2026-04-18

> 作者：Researcher session (Opus 4.7 1M)
> 工作目录：`/home/ops/projects/edu-cloud-t2`（master @ `5ec30de`）
> 审计基线：takeover commit `00cfc3d` (2026-04-16 21:21:23 +0800)
> 性质：只读审计，**不改代码 / 不改 plan / 不触 W4-R8 与 T-D 文件**
> 交接卡：`docs/plans/2026-04-18-takeover-audit-handoff.md`
> 完成时间：2026-04-18 09:12:32 起算

---

## §1. 审计结论（TL;DR）

1. **takeover (`00cfc3d`) 是一次有意的「ECS-as-authority 重置基线」事件**，不是技术故障也不是漏 sync — 证据：commit message 明写 `retire legacy ai/* modules; untrack uploads/ and *.db`；5 个被删 `tests/test_ai/` + 5 个被删 `src/edu_cloud/ai/{agent,context,intent_resolver,llm,llm_factory}.py` 全为 legacy；2054 个删除全集中在 `uploads/`。
2. **W4-R8 假设「takeover 遗失 40 测试」不成立**，应订正为 **「约 50 个 conduct 测试函数从未进入 git」(A 类：Windows-only 历史扩展)**。证据：`git log --all -- tests/test_conduct/` 唯一命中 `00cfc3d`，conduct 模块 src + tests 在 git 全历史的首现就是 takeover。
3. **plan baseline 漂移是系统性问题，横跨 ≥6 个 plan 文件**，但实际 grep 对账后 **6 项中 4 项契合 ECS 实测**（菜单 9=9 / services 15=15 / grading 10=10 / alembic 2→3 轻漂）、**2 项明显偏差**（conduct 118→68 / frontend conduct 3 件套 13→6）。
4. **ECS 与 Windows 差异主体是 `ai/*` legacy 被主动淘汰 + `uploads/` 被正当 untrack + conduct 模块约 50 个测试函数未提交**，没有证据显示"技术代码层面大规模漏 sync"。
5. **跟进优先级排序：T-H (ECS pytest 环境) > T-G (plan_baseline_guard hook) > T-F (plan 清洗)**。理由见 §6。

---

## §2. Takeover 全景

### 2.1 Commit 锚定

```
commit 00cfc3db747293ab8ebd0e55e6674efa62b970e1
Author: juanwan99 <linliangwan343@gmail.com>
Date:   Thu Apr 16 21:21:23 2026 +0800

    takeover: sync ECS worktree as authoritative; retire legacy ai/* modules; untrack uploads/ and *.db

 3492 files changed, 356697 insertions(+), 54790 deletions(-)
```

### 2.2 按状态分布

命令：`awk 'NR>6' /tmp/takeover-files.txt | awk '{print $1}' | sort | uniq -c`

| 状态 | 数量 |
|---|---|
| A (Add) | 778 |
| D (Delete) | 2067 |
| M (Modify) | 642 |
| R096/R097 (Rename) | 1 + 4 |
| **合计** | **3492 files**（与 shortstat 一致） |

### 2.3 按目录分桶

| 目录 | A | M | D | R | 备注 |
|---|---|---|---|---|---|
| `src/` | 113 | 208 | **5** | 0 | 5 删除全是 `ai/{agent,context,intent_resolver,llm,llm_factory}.py` |
| `tests/` | 103 | 168 | **5** | 0 | 5 删除全是 `tests/test_ai/test_{agent,agent_pipeline,context,intent_resolver,llm}.py` |
| `docs/` | 442 | 151 | 0 | 5 | 文档大规模新增 |
| `frontend/` | 63 | 87 | 3 | 0 | 小规模改动 |
| `alembic/` | 14 | 10 | 0 | 0 | 纯新增/修改 |
| `scripts/` | 9 | 2 | 0 | 0 | 小规模 |
| `uploads/` | 0 | 0 | **2054** | 0 | 全部 untrack（正当）|
| `其他` | 34 | 14 | 0 | 0 | dotfiles / root 级别 |

### 2.4 删除清单验证（与交接卡 §4 一致）

`awk '$1=="D" && $2 ~ /^tests\//' /tmp/takeover-files.txt`：

```
D	tests/test_ai/test_agent.py
D	tests/test_ai/test_agent_pipeline.py
D	tests/test_ai/test_context.py
D	tests/test_ai/test_intent_resolver.py
D	tests/test_ai/test_llm.py
```

对应 src 删除：

```
D	src/edu_cloud/ai/agent.py
D	src/edu_cloud/ai/context.py
D	src/edu_cloud/ai/intent_resolver.py
D	src/edu_cloud/ai/llm.py
D	src/edu_cloud/ai/llm_factory.py
```

**性质判定：C 类（takeover 主动 retire）**。message 显式声明 `retire legacy ai/* modules`，有意操作，无需恢复。

### 2.5 2054 个 `uploads/` 删除的正当性

`awk '$1=="D" && $2 !~ /^(src|tests|docs|alembic|frontend|scripts)\//' /tmp/takeover-files.txt | awk -F/ '{print $1"/"}' | sort | uniq -c`：

```
2054 uploads/
```

全部是 `uploads/` 下的用户上传文件（图片、PDF、切图等）。message 声明 `untrack uploads/ and *.db`，属正当把数据产物踢出 git。**性质：C 类**。

---

## §3. Plan Baseline 漂移清单（≥5 个 plan 核查）

### 3.1 对账方法

ECS 无法跑 pytest（`/usr/bin/python3` 存在但 `No module named pytest`，见交接卡 §3）。改用 `grep -c "def test_\|async def test_"` 实测函数数，并另行排查 `@pytest.mark.parametrize` 与 `class Test*`。

> **口径说明**：grep 得到的是"独立测试函数数"；plan baseline 的"X passed"是 pytest 执行后的 case 数。无 parametrize 时两者 1:1；有 parametrize 时 pytest > grep。

### 3.2 六项 plan × baseline × ECS 可执行性三栏表

| # | Plan 文件 | baseline 声称 | baseline 命令（已去 Windows 路径） | ECS 实测 | 判定 |
|---|---|---|---|---|---|
| 1 | `2026-04-14-conduct-roadmap-batch1-plan.md` L23 | **118 passed** | `pytest tests/test_conduct/ -q` | **68 函数**（0 parametrize / 0 class Test*）| **❌ 差 50 函数** |
| 2 | `2026-04-14-conduct-roadmap-batch1-plan.md` L24 | **15 passed** | `pytest tests/test_services/test_school_settings_service.py tests/test_services/test_homework_permissions.py` | **15 函数**（11+4）| ✓ |
| 3 | `2026-04-14-conduct-roadmap-batch1-plan.md` L25 | **13 passed** | `vitest run src/__tests__/sidebarConfig.conduct.test.js src/__tests__/AppSidebar.test.js src/pages/parent/__tests__/ParentRules.spec.js` | **6 个 it/test**（1+3+2）| **❌ 差 7 个** |
| 4 | `2026-04-12-haofenshu-phase1-plan.md` L489 | **9 passed** | `pytest tests/test_menu/test_menu_service.py` | **9 函数**（6+3 class-based） | ✓ |
| 5 | `2026-04-13-migration-gate-repair-design.md` L180 | **2 passed** | `pytest tests/test_alembic_migration.py -q` | **3 函数** | **⚠ plan 过时 (+1)** |
| 6 | `2026-04-12-grading-dispatch-plan.md` L181 | **10 passed** | `pytest tests/test_services_exam/test_objective_grading.py -v` | **10 函数**（class Test*）| ✓ |

**补充 kg-phase1**（`2026-04-13-knowledge-graph-phase1-plan.md`）整体 baseline 未在 plan 中以"X passed"格式给出，但 `tests/test_knowledge_tree/` 目录 **20 文件 / 160 函数** 全部存在、可寻址。

### 3.3 Windows 路径命中文件规模

Grep `cd C:/Users/Administrator` 于 `docs/plans/*.md` → 100 文件命中（触及 head_limit，实际更多）。说明 Windows 路径 baseline 命令**系统性扩散**到绝大多数 plan，但实际测试文件和命名空间在 ECS 上**主要可达**（除 `cd /...` 和 `pytest` 二进制两个外壳差异）。

---

## §4. conduct 特例对账

### 4.1 git 历史中的 conduct 模块

```
$ git log --all --oneline --reverse -- 'tests/test_conduct/'
00cfc3d takeover: sync ECS worktree as authoritative; ...

$ git log --all --oneline --reverse -- 'src/edu_cloud/modules/conduct/'
00cfc3d takeover: sync ECS worktree as authoritative; ...
```

**唯一 commit 就是 takeover**。不存在任何 pre-takeover 的 conduct commit — 这直接推翻"takeover 丢了 40 个测试"的假设：git 仓里 conduct 模块从未有过比 takeover 更完整的版本。

### 4.2 conduct pytest baseline 的 Windows-era 时序

| 日期 | 来源 | 数字 |
|---|---|---|
| 2026-04-12 | `2026-04-12-conduct-module-review-report-batch1.md` L15 | 78 passed（codex 实测） |
| 2026-04-12 | `2026-04-12-conduct-module-review-report-batch1-r2.md` L210 | **108 passed**（R2 基线）|
| 2026-04-13 | `2026-04-13-conduct-next-phase-handoff.md` L151 | 120 passed（R3 收尾 108+12） |
| 2026-04-14 | `2026-04-14-conduct-roadmap-batch1-plan.md` L23/L84 | **118 passed**（R3 订正 108+10） |
| 2026-04-16 | takeover commit `00cfc3d` 发生 | — |
| 2026-04-18 | ECS grep 实测（本 audit） | **68 函数**（无 parametrize / 无 class Test*） |

### 4.3 差值归因

Windows 118 − ECS 68 = **50 个测试函数从未进入 git**。按归类决策矩阵属于 **A 类：Windows-only 历史扩展**。恢复路径有三条：
- A1. Windows 开发环境仍可达 → 从 Windows worktree 增量 sync 过来（需用户确认 Windows 状态）
- A2. Windows 不可达 → 按 R2/R3 handoff 记载的测试列表重新实现
- A3. 用户决定 ECS 68 已够用 → 将 Windows 118 baseline 订正为 68（但须同步修订 CLAUDE.md 与所有 plan 中的 118/120/108 数字）

### 4.4 对 W4-R8「40 测试遗失」假设的权威结论

- **「40」数字的来源不清**。遍历 `docs/plans/*.md` 与 `docs/plans/*.log` 未找到 `40 passed` 级别的 conduct 基线证据；最接近的是 plan 「118 passed」与 ECS grep 「68 函数」的差值 **50**（非 40）。建议 W4-R8 Planner 将 handoff 里的「40」订正为「约 50 个测试函数」或 `118 − 68 = 50`，避免再次数字漂移。
- **归类：A 类（Windows-only 历史扩展，git 无源头，takeover 无过失）**。这与交接卡 §1 的预判一致。

---

## §5. 归类决策矩阵

| 类型 | 定义 | 实例 | 处置建议 |
|---|---|---|---|
| **A** | Windows-only 历史扩展（git 无源头）| conduct 50 个测试函数 + frontend conduct 3 件套 约 7 个 it/test | 用户决策 A1/A2/A3 之一；默认 A3（接受 ECS 现状） |
| **B** | git 历史有 commit 但未 sync 到 ECS（可 cherry-pick）| **本次审计未发现任何 B 类漂移** | — |
| **C** | takeover 主动 retire，无需操作 | `tests/test_ai/*.py` × 5 + `src/edu_cloud/ai/{agent,context,intent_resolver,llm,llm_factory}.py` × 5 + `uploads/` × 2054 | 无需操作 |
| **D** | plan 引用但代码从未存在（plan 错误，需修订）| `migration-gate-repair-design.md` 的「alembic 2 passed」(ECS 实测 3 函数，plan 数字过时) | T-F 统一清洗：baseline 数字加 `verified_at` 元信息 |

**覆盖率审计**：本次对 6 项 plan baseline 命令进行核查，其中 4 项与 ECS 一致（含 alembic 轻漂）、2 项明显偏差（conduct 50 / frontend conduct 7）；未发现 B 类缺漂。结论：**ECS 与 Windows 的"技术代码"差异面极小，主要差异集中在 conduct 模块测试** — 而 conduct 的全部测试（包括已 sync 的 68 个）在 git 中就是 takeover 首现，不存在"历史 commit 漏 sync"。

---

## §6. Followup 建议（T-F / T-G / T-H 优先级）

### 6.1 依赖关系

```
┌────────────────────────┐       ┌────────────────────────┐
│ T-H: ECS pytest 环境   │◀──────│ T-G: baseline_guard    │◀─┐
│ （P0，最根部）          │       │ hook（P1）              │  │
└────────────────────────┘       └────────────────────────┘  │
       ▲                                                      │
       │                         ┌────────────────────────┐   │
       └─────────────────────────│ T-F: plan baseline     │◀──┘
                                 │ 清洗 + verified_at      │
                                 │ 元信息（P2）             │
                                 └────────────────────────┘
```

### 6.2 优先级与理由

| 优先级 | 任务 | 理由 | 依赖 |
|---|---|---|---|
| **P0** | **T-H（ECS pytest 环境）** | 当前 ECS `No module named pytest` 阻塞所有 L2 （pytest cases 级别）验证。没有 pytest，任何 baseline 真伪最终只能依赖 grep 的 L1 验证（函数级别），无法复现 parametrize 展开后的真实 pass 数。T-G/T-F 的价值都依赖 T-H 先落地。 | 无 |
| **P1** | **T-G（plan_baseline_guard hook）** | 防止未来 plan 再写 Windows-only `cd C:/...` 路径 baseline + 数字漂移。hook 可基于本次审计发现建立 allowlist：允许 `pytest {path}` 不带 `cd`、拦截含 `cd C:/Users/` 的 bash block、对"X passed"数字要求与 `verified_at` 同行。 | T-H（hook 需真实 pytest 验证数字才有意义）|
| **P2** | **T-F（plan 清洗）** | 系统性修订旧 plan 的 baseline 数字 + 路径。基于本次 audit 报告的归类决策（§5）批量处理 D 类条目；A 类数字保留 `verified_at` + 标注 "Windows-era, ECS=? pending T-A/T-B"。 | T-E（本任务）、T-G（hook 落地后才能防回退） |

### 6.3 W4-R8 Planner 动作建议（不强制）

- 订正 W4-R8 `2026-04-18-w4-r8-planner-handoff.md` 中「40 测试遗失」→「约 50 个测试函数（Windows 118 - ECS 68）属 Class A Windows-only 历史扩展」；
- 订正 CLAUDE.md「120 conduct tests」条目至当前 ECS 实测（68 函数 / Windows baseline 118）；
- conduct-roadmap batch1 plan 目前 baseline 118 虽然"漂移"，但 **W4-R8 自己的后续 plan step 可以继续用 118 作为 Windows 验证 baseline**；只有当迁到 ECS 验证环境后，才有必要把 baseline 订正为 ECS 实测值。

---

## §7. 审计过程证据清单（可复现）

| 编号 | 命令 | 输出摘要 |
|---|---|---|
| E-01 | `git log -1 --format="%H %s"` | `5ec30de ... docs: 派发 T-E + T-G 交接卡` |
| E-02 | `git log --all --grep="takeover" --format="%H %ad %s"` | `00cfc3d 2026-04-16 21:21:23 +0800 takeover: ...` |
| E-03 | `git show --shortstat 00cfc3d` | `3492 files changed, 356697 insertions(+), 54790 deletions(-)` |
| E-04 | `git show --name-status 00cfc3d > /tmp/takeover-files.txt && awk ... | sort | uniq -c` | A=778 / D=2067 / M=642 / R=5 |
| E-05 | `awk '$1=="D" && $2 ~ /^tests\//'` | 5 条全部 `tests/test_ai/*.py` |
| E-06 | `awk '$1=="D" && $2 ~ /^src\//'` | 5 条全部 `src/edu_cloud/ai/*.py` |
| E-07 | `grep -c "def test_" tests/test_conduct/*.py` | 总 68 函数（13+14+9+4+4+19+5） |
| E-08 | `grep -c parametrize tests/test_conduct/*.py` | 全 0 |
| E-09 | `grep "^class Test" tests/test_conduct/*.py` | 零命中 |
| E-10 | `git log --all --oneline -- tests/test_conduct/` | 唯一 commit `00cfc3d` |
| E-11 | `git log --all --diff-filter=A -- src/edu_cloud/modules/conduct/__init__.py` | 唯一 commit `00cfc3d` |
| E-12 | `grep -c "def test_" tests/test_menu/*.py` | 3+6=9（class-based） |
| E-13 | `grep -c "def test_" tests/test_alembic_migration.py` | 3（plan 写 2） |
| E-14 | `grep -c "def test_" tests/test_services_exam/test_objective_grading.py` | 10 |
| E-15 | `grep -cE "(it|test)\(" frontend/src/__tests__/sidebarConfig.conduct.test.js frontend/src/__tests__/AppSidebar.test.js frontend/src/pages/parent/__tests__/ParentRules.spec.js` | 1+3+2=6（plan 写 13） |

---

## §8. 本次审计未做（明确声明）

- 未运行任何 pytest / vitest（ECS 环境不支持，符合红线）
- 未访问或修改 `docs/plans/2026-04-18-w4-r8-planner-handoff.md`、`docs/plans/2026-04-18-w2-batch3b-iii-handoff.md`、以及 W4-R8 branch 下的 `batch1-baseline-evidence.md`
- 未修改任何 `src/*`、`frontend/*`、`alembic/*`、`docs/plans/*.md`（除本报告新文件）
- 未触发任何 codex-review / deep-review / codex 咨询
- 未尝试恢复 Windows 历史测试（决策权在用户）

---

**本报告基于事实与 commit anchor，禁猜测。L013（自审盲区）/L015（虚假完成声明）严守。**
