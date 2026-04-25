---
type: evidence
topic: conduct-roadmap-batch1-baseline
created: 2026-04-18 08:20:00
updated: 2026-04-18 13:28 (T-Wipe Phase 5 rewrite)
baseline_command: "pytest tests/test_conduct/ -q"
baseline_verified_at: "2026-04-18 10:25:04"
baseline_count: 68
baseline_method: pytest
baseline_note: "ECS pytest 实测（takeover 00cfc3d 后 ECS 单一权威环境，L018）。"
---

# Batch 1 Baseline Evidence · ECS 单一环境实测

> 触发：Executor @ T3 Step 1.1 实测偏差，按 bug-fix-discipline 停手。
> 作者：Executor session @ `/home/ops/projects/edu-cloud` HEAD `637ce2f`
> 时间：2026-04-18 08:20 UTC+8（实测）；T-Wipe Phase 5 重写 2026-04-18 13:28 UTC+8
> 文件性质：**证据报告**，非 handoff.md，不触发 handoff_format_guard。
>
> **架构边界**：ECS 是单一权威开发环境（takeover `00cfc3d` 后，L018）。
> 本文档只含 ECS pytest 实测数字 + 来源命令，不引历史对比。

## 1. ECS 实测基线 @ HEAD `637ce2f`

| 路径 / 命令 | ECS 实测 | 备注 |
|---|---|---|
| `pytest tests/test_conduct/ -q` | **68 passed** | exit 0, ~37s |
| `pytest tests/test_services/test_school_settings_service.py tests/test_services/test_homework_permissions.py -q` | 15 passed | exit 0 |
| plan §5 组合（+ `test_api/test_deps.py`） | **87 passed** | 68 + 15 + 4 |
| `npx vitest run` 全量 | 234 passed | 24 files |
| conduct 前端三件套 | 13 passed | `sidebarConfig.conduct 8` + `AppSidebar 3` + `ParentRules 2` |
| `sidebarConfig.conduct.test.js` 单文件 | 8 passed | |
| `AppSidebar.test.js` | 3 passed | |
| `ParentRules.spec.js` | 2 passed | |

### 1.1 conduct 前端三件套（真实位置）

```
src/__tests__/sidebarConfig.conduct.test.js     8 tests
src/__tests__/AppSidebar.test.js                3 tests
src/pages/parent/__tests__/ParentRules.spec.js  2 tests
合计                                            13 tests
```

## 2. Plan 数字 ECS 订正已完成（post-T-Wipe 2026-04-18 Phase 4）

T-Wipe Phase 4（master commit `3591ab4` + W4 commit `051cc35`）已把 plan
`2026-04-14-conduct-roadmap-batch1-plan.md` 按 ECS 上下文全文 ECS-rewrite：

- `baseline_count: 68`，`baseline_verified_at: 2026-04-18 10:25:04`，`baseline_method: pytest`
- 退出条件：conduct ≥ 80 passed（68 ECS 基线 + ~12 增量：T4+3 / T1+6 / T2+3）
- 各 Task Expected：71 / 77 / 80（基于 68 基线）
- 命令路径：`cd /home/ops/projects/edu-cloud` + `.venv/bin/python`
- state.json 已创建：`docs/plans/2026-04-14-conduct-roadmap-batch1-state.json`，`conduct_backend: 68`

T5 任务降级为 post-T-Wipe 验证（CLAUDE.md 由 T-Wipe Phase 3 `6d4126e` 覆盖，Executor 仅需校验一致性 + 必要时处置 next-phase handoff 残留）。

## 3. Gate 1 状态（不变更）

CLAUDE.md 参考文档条目声明 `Gate 1 R7 PASS ✅ (2026-04-18)` + `code_review_batch1 解锁 pending_execution`。本证据报告不改变 Gate 1 状态——R8 选择 **方案 [b]**：T-Wipe Phase 4 直接订正 plan 数字，不重走审查。Planner 已决策 T-Wipe 覆盖全局清洗，R1-R7 review 资产的**结构性修订**（F001-F007 / Contract Pack / 入口级测试）保留。

## 4. 推算清单（基于 ECS 基线 68）

| Task 完成后 conduct 后端 | 新增 | 累计 |
|---|---|---|
| T4 (3 governance) | +3 | 71 |
| T1 (4 helper + 1 API 403 + 1 对照组) | +6 | 77 |
| T2 (3 入口级) | +3 | 80 |
| **最终目标** | | **80 passed** |

frontend 累计（ECS 基线 234 + plan 新增 16）：**250 passed**。
services 累计：**15 passed**（不变）。

## 5. 可复现命令清单（ECS 单一环境）

```bash
cd /home/ops/projects/edu-cloud

# conduct 后端
.venv/bin/python -m pytest tests/test_conduct/ -q --tb=no       # 68 passed

# services
.venv/bin/python -m pytest tests/test_services/test_school_settings_service.py tests/test_services/test_homework_permissions.py -q --tb=no  # 15 passed

# plan §5 组合
.venv/bin/python -m pytest tests/test_conduct/ tests/test_services/test_school_settings_service.py tests/test_services/test_homework_permissions.py tests/test_api/test_deps.py -q --tb=no  # 87 passed

# frontend 全量
cd frontend && npx vitest run   # 234 passed / 24 files

# conduct 三件套
npx vitest run src/__tests__/AppSidebar.test.js src/__tests__/sidebarConfig.conduct.test.js src/pages/parent/__tests__/   # 13 passed / 3 files
```

## 6. Executor 停手位置

- HEAD `637ce2f`，分支 `feat/conduct-roadmap-batch1`
- Working tree: `M test_output/tql_yuwen_a3.pdf`（plan §4 已承认 OK）
- 未新增 staged / untracked 生产代码
- 本证据报告由 T-Wipe Phase 5（2026-04-18）重写为 ECS 单一环境视角，删除历史对比表 / 外部文档路径 / "Plan 声称 vs 实测" 段
