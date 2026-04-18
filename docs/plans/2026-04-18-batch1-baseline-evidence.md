# Batch 1 Baseline Evidence · Planner R8 必读

> 触发：Executor @ T3 Step 1.1 实测偏差，按 bug-fix-discipline 停手。
> 作者：Executor session @ `/home/ops/projects/edu-cloud` HEAD `637ce2f`
> 时间：2026-04-18 08:20 UTC+8（当前会话实跑）
> 文件性质：**证据报告**，非 handoff.md，不触发 handoff_format_guard。

## 1. 症状

Plan `2026-04-14-conduct-roadmap-batch1-plan.md` Task 1 Step 1.1 expected `118 passed`，实测 **68 passed**。差 -50。深入核对后发现 plan 多处"基线 + N 新增 = M passed"计算式全部以伪基线（118）为起点。

## 2. 实测基线（当前 HEAD `637ce2f`）

| 路径 / 命令 | Plan 声称 | 实测 | 偏差 | 备注 |
|---|---|---|---|---|
| `pytest tests/test_conduct/ -q` (L24/L82/L88/L111) | 118 | **68** | -50 | pytest `--collect-only` 亦 68；非 deselect |
| `pytest tests/test_services/test_school_settings_service.py tests/test_services/test_homework_permissions.py -q` (L25) | 15 | 15 | 0 | ✅ |
| plan §5 组合 (+ `test_api/test_deps.py`) | — | **87** | — | 68 + 15 + 4 |
| `npx vitest run` 全量 (L1529) | 234 | 234 | 0 | ✅ 今日早上校准过 |
| `npx vitest run src/pages/conduct/ src/components/shell/` (L30, §5 命令) | — | **0** (No files) | — | ❌ 路径错，这俩目录下无测试文件 |
| conduct 前端三件套 (L1683) | 13 | 13 | 0 | ✅ |
| `sidebarConfig.conduct.test.js` 单文件 (L1517) | 13 | **8** | -5 | ❌ 把"三件套合计 13"误拆为"单文件 13" |
| `AppSidebar.test.js` | 3 | 3 | 0 | ✅ |
| `ParentRules.spec.js` | 未说 | 2 | — | — |

### 2.1 conduct 前端三件套（真实位置）

```
src/__tests__/sidebarConfig.conduct.test.js     8 tests
src/__tests__/AppSidebar.test.js                3 tests
src/pages/parent/__tests__/ParentRules.spec.js  2 tests
合计                                            13 tests ✅
```

## 3. Plan 中需订正的数字锚点（按行号）

| 行 | 原 | 问题 | 建议（供 Planner 决策，不绑定） |
|---|---|---|---|
| L24 | `118 passed, 237.52s, exit 0` | 伪数字 | `68 passed, ~37s, exit 0` |
| L25 | `15 passed, 10s` | ✅ 正确 | 无 |
| L29 | `conduct 后端 ≥ 130 passed` | 基于 118 | `≥ 80 passed`（68 + 3 + 4 + 1 + 1 + 3） |
| L82 | `baseline 仍是 118` | 伪 | `baseline 为 68` |
| L88 | `118 passed in ...s, 1 warning` | 伪 | `68 passed in ...s` |
| L94 | `grep "120 conduct tests\|108 + 12"` | 源头"120/108+12"整条伪 | Planner 重新审视 CLAUDE.md 德育条目该怎么描述 conduct 测试数 |
| L101-102 | `120 → 118` + `108 + 12 → 108 + 10` | 从伪改伪 | 改为"实测 68"或扩大 Task 1 scope |
| L111 | `# 期望: 118 passed (R3 收尾基线)` | 伪 | 68 或由 Planner 决定 |
| L149-153 commit 叙事 | "修正 120→118 漂移"+"实测 118 passed 237.52s" | 整体叙事伪 | Planner 重写 commit message 叙事 |
| L166 | `R3 handoff 原本就是 118，无需改` | 可能也伪 | Planner 核验 2026-04-12-conduct-module-review-handoff-batch1-r3.md |
| L441 | `121 passed (118 基线 + 3 governance)` | 118 基线错 | `71 passed (68 + 3)` |
| L842 | `127 passed (118 + 3 + 4 + 1 + 1)` | 118 基线错 | `77 passed (68 + 3 + 4 + 1 + 1)` |
| L1112 / L1671 | `130 passed (118 + 3 + 4 + 1 + 1 + 3)` | 118 基线错 | `80 passed (68 + 3 + 4 + 1 + 1 + 3)` |
| L1517 | `sidebarConfig.conduct.test.js 原 13 + 新 9 + 新 1 = 23` | 单文件原基线应为 8 | `8 + 9 + 1 = 18`（若 plan 新增设计不变） |
| L1529 | `234 + 16 = 250` | ✅ 对 | 无 |
| L1585 | `合计 conduct 前端套件 29 passed` | 13 基线对 → `13 + 16 = 29` ✅ | 无 |
| L1677 | `15 passed`（services） | ✅ 对 | 无 |
| L1683 | `29 passed (13 + 16)` + `130 passed (conduct 后端)` | 前半对；后半 130 基于 118 错 | conduct 后端应为 80 |

## 4. 共带影响的外部文档

- **`C:/Users/Administrator/edu-cloud/CLAUDE.md`** 德育条目：`120 conduct tests（R2 基线 108 + 12 新增）` — 同为伪数字，Task 1 原设计只是"从伪改伪"。Planner 需审视该条目应如何修正才和实测一致。
- **`docs/plans/2026-04-13-conduct-next-phase-handoff.md:151`** `# 期望: 120 passed (R3 收尾基线)` — 同源伪。
- **`docs/plans/2026-04-12-conduct-module-review-handoff-batch1-r3.md`**（plan L166 声称"原本就是 118，无需改"）— 需 Planner 核验是否真是 118 或也是伪。
- **`state.json`**（`2026-04-14-conduct-roadmap-batch1-state.json`）— **不存在**。plan §"state.json 生命周期（F004 修复）"说"由 Planner 在 Gate 1 PASS 后 Step 0 创建"，但 Planner 未做。每个 Task 的 Step X.0 和 X.5a 都依赖此文件。

## 5. Gate 1 / gates.json 状态影响

CLAUDE.md 参考文档条目已声明 `Gate 1 R7 PASS ✅ (2026-04-18)` + `code_review_batch1 解锁 pending_execution`。但基线伪 → **Gate 1 R1-R7 七轮审查 Reviewer 从未实跑基线命令**，review 资产的"PASS"判定基于伪数据。

按 L017（GPT 局部最优覆盖全局最优）的对偶：这里是 **Reviewer 文字审覆盖实测审**。Planner 需决定：

- [a] Gate 1 状态回退到 `under_review_r8`，订正基线后重新走 R8 审查
- [b] Gate 1 保持 PASS，仅 R8 做"数字订正补丁"（不重走审查）
- [c] 其他

## 6. 推算清单（供 Planner 参考，非绑定）

基于实测基线 68 + plan 设计的各 Task 新增测试数：

| Task 完成后 conduct 后端 | 新增 | 累计（实测基础） | Plan 原值（118 基础） |
|---|---|---|---|
| T4 (3 governance) | +3 | 71 | 121 |
| T1 (4 helper + 1 API 403 + 1 对照组) | +6 | 77 | 127 |
| T2 (3 入口级) | +3 | 80 | 130 |
| **最终目标** | | **80 passed** | 130 passed |

frontend 累计（实测基线 234 + 新增 16）：**250 passed** ✅ 不变。
services 累计：**15 passed** ✅ 不变。

## 7. Executor 未做的事

- 未 commit 任何文件（包括本文件）
- 未改 plan / CLAUDE.md / state.json
- 未跑 `test_output/tql_yuwen_a3.pdf` 以外的 git 改动（仅 plan L21 默认飘动）
- 未核验 R3 handoff L171"原本就是 118"真伪（Planner 需核）
- 未调查"118 passed, 237.52s" 这组数字源头（可能是 plan 作者从 R3 handoff 抄的，或纯编造）

## 8. 可复现命令清单

```bash
cd /home/ops/projects/edu-cloud

# conduct 后端
.venv/bin/python -m pytest tests/test_conduct/ -q --tb=no      # 68 passed

# services（plan L25 字面命令）
.venv/bin/python -m pytest tests/test_services/test_school_settings_service.py tests/test_services/test_homework_permissions.py -q --tb=no   # 15 passed

# plan §5 组合
.venv/bin/python -m pytest tests/test_conduct/ tests/test_services/test_school_settings_service.py tests/test_services/test_homework_permissions.py tests/test_api/test_deps.py -q --tb=no   # 87 passed

# frontend 全量
cd frontend && npx vitest run   # 234 passed / 24 files

# conduct 三件套（真实位置）
npx vitest run src/__tests__/AppSidebar.test.js src/__tests__/sidebarConfig.conduct.test.js src/pages/parent/__tests__/   # 13 passed / 3 files
```

## 9. Executor 停手位置

- HEAD `637ce2f`，分支 `feat/conduct-roadmap-batch1`
- Working tree: `M test_output/tql_yuwen_a3.pdf`（plan §4 已承认 OK）
- 未新增 staged / untracked 生产代码
- 本证据报告未 commit（等用户 + Planner 决策）

> Planner R8 session 启动建议：读本文件 → 核验 §8 命令 → 按 §5 [a/b/c] 决策 Gate 1 状态 → 订正 plan 所有锚点 → 处理 CLAUDE.md/next-phase-handoff 的伪数字 → 走独立审查。
