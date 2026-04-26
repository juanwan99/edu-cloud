---
type: planner-handoff
created: 2026-04-10 22:23:23
project_dir: C:\Users\Administrator\edu-cloud
design: C:\Users\Administrator\edu-cloud\docs\plans\2026-04-10-teacher-workbench-phase2.5-design.md
plan: C:\Users\Administrator\edu-cloud\docs\plans\2026-04-10-teacher-workbench-phase2.5-plan.md
---

# 知识图谱教师工作台 Phase 2.5 — Planner 接手交接卡

## 约束与偏好

**T3 流程**。Phase 2.5 清理 Phase 2 的两条 test_debt，Gate 1 Plan Review **PASS R2**。

### 当前位置（写卡时）

- `docs/plans/2026-04-10-teacher-workbench-phase2.5-state.json` → 3 Tasks 全 `completed`（Executor 代码实现已落盘）
- `docs/plans/2026-04-10-teacher-workbench-phase2.5-gates.json` → `plan_review: pass`，`code_review_batch1` **未写**
- `docs/plans/2026-04-10-teacher-workbench-phase2.5-review-handoff-batch1.md` **不存在**
- `docs/plans/2026-04-10-teacher-workbench-phase2.5-review-report-batch1.md` **不存在**

**结论**：Executor 做完代码但未写审查交接单、未调 codex-review。你接手时要先判断 Executor 是卡在自审 / 还没送审 / 已送审但文件未 push 同步——通过 git log 看最新 commit 时间和 commit message 判断。

### Planner 接手后的决策树

```
Gate 2 尚未送审（当前状态）
  ├── Executor 卡在自审/反证 → 等 Executor 完成，不要替他写审查交接单
  ├── Executor 已完成但忘了调 codex-review → 提醒 Executor 在其会话内调用
  └── Executor 会话已结束，需要新 Planner 或新 Executor 跑送审 → 重开一个 Executor 会话完成剩余送审步骤

Gate 2 PASS
  → 在 design.md 头部追加 `[YYYY-MM-DD HH:MM:SS 实现完成] Commits: {first}..{last}`
  → state.json 添加 closed=true + closure_note
  → 更新 CLAUDE.md 参考表状态为 [实现完成]
  → 输出视觉验收待办（design §8 的 3 条浏览器路径）给用户
  → commit: "design: teacher-workbench phase2.5 implementation complete"

Gate 2 FAIL
  → 按 review-templates.md 3 轮循环
  → L017 守卫：behavior_change finding 必须单独呈现，禁止批量批准
  → Round 1-2 由 Executor 修复；Round 3 需 Planner 介入分类（code-bug 要修 / design-concern 记 §待处置）
```

### 关键红线（Executor 代码实现必须保持）

这些是 Gate 1 R1 FAIL 后 R2 修复的硬约束。审查 Executor 实现时**必须**逐条核对，任何一条回归都要退回修复：

| ID | 红线 |
|----|------|
| F001 | `focusedNodeId` 保持组件内部 `ref`，不是 prop；watch 监听内部 ref |
| F002 | `defineExpose` 增量扩展，**保留** Phase 2 已暴露的 `focusedNodeId` 和 `clearFocus` |
| F003 | edge id 规则通过 `buildVisibleEdgeList()` helper 统一，`buildG6Data` 和 `relatedEdgeIds` 共用 |
| F004 | `createGraph()` 末尾 `if (focusedNodeId.value) nextTick(updateElementStates)` 重放焦点 |
| F005 | 测试真实断言 `graph.setElementState.mock.calls`，禁止逻辑镜像 |
| F006 | Tooltip plugin 测试读 `graphCtorCalls[last].plugins` 真实 wiring，禁止手写等价谓词 |
| F007 | 桥接/对比边 disposition = `deferred → Phase 3`（不是 resolved） |
| F008 | design §3 `relatedNodeIds`/`relatedEdgeIds` 代码示例已对齐 plan 最终口径 |

详见 `docs/plans/2026-04-10-teacher-workbench-phase2.5-plan-review-report.md`「R1 finding 处置状态」段。

### 关键文件索引（绝对路径）

- 计划/设计/状态 → YAML front matter 已列
- **Gate 1 R2 PASS 报告**: `C:\Users\Administrator\edu-cloud\docs\plans\2026-04-10-teacher-workbench-phase2.5-plan-review-report.md`
- **Executor handoff**: `C:\Users\Administrator\edu-cloud\docs\plans\2026-04-10-teacher-workbench-phase2.5-handoff.md`（含 Executor 启动 Prompt 和 6 条硬约束详解）
- **R1/R2 原始审查日志**: `docs/plans/.codex-plan-review-phase2.5-raw.log` / `docs/plans/.codex-raw-plan_review-phase2.5-r2-20260410T214500.log`
- **Phase 2 本体（只读）**: `docs/plans/2026-04-10-teacher-workbench-design.md` `[实现完成]` commits 7a5ecfb..549e298
- **核心改动点**: `frontend/src/components/knowledge-tree/ConceptMapPanel.vue` + `frontend/src/__tests__/knowledge-tree/ConceptMapPanel.test.js`

### Planner 纪律（R1 事故教训）

1. **写 plan 前必须 Read 现有代码**。R1 FAIL 根因是 Planner 凭印象假设 API，plan 与实际代码脱钩。本次 R2 已修，Executor 实现时再审查若回到老问题（props.focusedNodeId 等），退回重审。
2. **视觉任务验收权在用户**。Planner 收尾时不要自行宣布"Phase 2.5 完成"，必须列出浏览器 3 条验收路径（design §8）让用户手动走。
3. **behavior_change 不可批量**。L017 守卫，Gate 2 如有 behavior_change finding 必须单独呈现，等用户逐条 `批准 F00X` / `拒绝 F00X`。
4. **不要默认自治**。Planner 接手的第一句话应该是"我在 X 位置，下一步计划是 Y，请确认或调整方向"，等用户点头再推进。

## 启动 Prompt

```
[edu-cloud] Planner | 2026-04-10 22:23:23
项目: C:\Users\Administrator\edu-cloud
读取 C:\Users\Administrator\edu-cloud\docs\plans\2026-04-10-teacher-workbench-phase2.5-planner-handoff.md 了解交接上下文。然后执行以下接手诊断：
1. 读 C:\Users\Administrator\edu-cloud\docs\plans\2026-04-10-teacher-workbench-phase2.5-state.json 确认 Tasks 状态
2. 读 C:\Users\Administrator\edu-cloud\docs\plans\2026-04-10-teacher-workbench-phase2.5-gates.json 确认 Gate 2 (code_review_batch1) 当前状态
3. 检查 docs/plans/2026-04-10-teacher-workbench-phase2.5-review-handoff-batch1.md 和 -review-report-batch1.md 是否存在
4. git log --oneline -10 查 Executor 最新动作
基于以上诊断，向用户汇报：
- 当前 Phase 2.5 所处位置（Executor 代码完成 / 自审完成 / 送审完成 / Gate 2 结果）
- 下一步计划（按 planner-handoff.md 的决策树选分支 A Gate 2 收尾 / 分支 B FAIL 处置 / 分支 C 等 Executor 完成剩余步骤）
- 等用户确认或调整方向后再推进，禁止默认自治。
保持 Planner 身份，不要自己写代码或调 codex-review——这些由 Executor 身份完成。如 Gate 2 还未送审，提示用户派发 Executor 会话完成剩余送审步骤。
```
