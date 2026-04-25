---
type: handoff
created: 2026-04-10 22:03:48
project_dir: C:\Users\Administrator\edu-cloud
design: C:\Users\Administrator\edu-cloud\docs\plans\2026-04-10-teacher-workbench-phase2.5-design.md
plan: C:\Users\Administrator\edu-cloud\docs\plans\2026-04-10-teacher-workbench-phase2.5-plan.md
---

# 知识图谱教师工作台 Phase 2.5 — 执行会话交接卡

## 约束与偏好

**T3 流程**。Phase 2.5 是 Phase 2（已实现完成）的延后项清理，Gate 1 Plan Review 已 **PASS R2**。本卡用于新会话按 plan 执行 Batch 1（Task 1-3）。

### 前置状态（只读，不要改动）

- **plan**: `C:\Users\Administrator\edu-cloud\docs\plans\2026-04-10-teacher-workbench-phase2.5-plan.md`（Gate 1 PASS R2，commit 38fc161）
- **design**: `C:\Users\Administrator\edu-cloud\docs\plans\2026-04-10-teacher-workbench-phase2.5-design.md`
- **state**: `C:\Users\Administrator\edu-cloud\docs\plans\2026-04-10-teacher-workbench-phase2.5-state.json`（3 Tasks 全 pending）
- **gates**: `C:\Users\Administrator\edu-cloud\docs\plans\2026-04-10-teacher-workbench-phase2.5-gates.json`（plan_review: pass）
- **Gate 1 R2 审查报告**: `C:\Users\Administrator\edu-cloud\docs\plans\2026-04-10-teacher-workbench-phase2.5-plan-review-report.md`
- **Phase 2 本体**: `C:\Users\Administrator\edu-cloud\docs\plans\2026-04-10-teacher-workbench-plan.md`（`[实现完成]` commits 7a5ecfb..549e298，**严禁改动**）

### 执行范围

**单一改动点**：`frontend/src/components/knowledge-tree/ConceptMapPanel.vue` + `frontend/src/__tests__/knowledge-tree/ConceptMapPanel.test.js`。**无后端改动**。**无新依赖**。

3 Task 1 Batch，估算 ~300 LOC（组件 +120~150 / 测试 +150~200）。期望前端全量 17 files / 178 tests PASS（Phase 2 的 160 + Phase 2.5 的 18）。

### R1 修复硬约束（不可回退）

Plan R1 曾 FAIL（7 finding），R2 PASS。以下是**必须坚守**的红线，否则 Executor 会把 R1 老问题写回去：

1. **F001 硬约束 — focusedNodeId 是组件内部 ref**
   - `ConceptMapPanel.vue:87` 已有 `const focusedNodeId = ref(null)`
   - Phase 2.5 的新 computed / watch / updateElementStates **必须**读 `focusedNodeId.value`
   - **严禁**改成 `props.focusedNodeId`
   - **watch** 写法: `watch(focusedNodeId, () => nextTick(updateElementStates))`，**不是** `watch(() => props.focusedNodeId, ...)`

2. **F002 硬约束 — defineExpose 增量扩展**
   - `ConceptMapPanel.vue:289` 现有 `defineExpose({ crossModuleBadges, crossModulePeers, focusedNodeId, clearFocus })`
   - Phase 2.5 **必须保留** 全部 4 个原字段，在其上 append 新字段
   - **严禁**写成 `{ crossModuleBadges, crossModulePeers, relatedNodeIds, relatedEdgeIds, ... }`（删掉 focusedNodeId/clearFocus 会让 Phase 2 多处测试红，见 ConceptMapPanel.test.js:215/221/235 等）

3. **F003 硬约束 — edge id 规则统一走 helper**
   - 新增 `buildVisibleEdgeList()` helper（plan Task 1 Step 1 代码）
   - `buildG6Data()` 的现有 `g6Edges` 构建**必须**改为调 helper
   - `relatedEdgeIds` computed **必须**用 helper 的 `visibleId`
   - **严禁**用 `props.edges.forEach((e, i) => { id: \`edge-${i}\` })`（原始索引，有 dangling edge 时会偏移）
   - Task 1 测试 6（`F003 guard: buildVisibleEdgeList skips edges...`）是这条约束的反证护栏

4. **F004 硬约束 — createGraph 末尾重放焦点**
   - `createGraph()` 末尾（`graph.on(...)` 之后）必须 append:
     ```js
     if (focusedNodeId.value) { nextTick(updateElementStates) }
     ```
   - Task 2 测试 `F004 graph rebuild` 是反证护栏，通过 `setProps({ nodes: newNodes })` 驱动 destroy→create 循环，断言**新** graph 实例的 setElementState 被重放调用

5. **F005 硬约束 — G6 mock 扩展 setElementState spy**
   - 在 `ConceptMapPanel.test.js:7-27` 现有 mock 的 `class Graph { constructor(cfg) { ... }}` 内新增一行：
     ```js
     this.setElementState = vi.fn().mockResolvedValue(undefined)
     ```
   - 测试断言真实 spy 调用: `graph.setElementState.mock.calls[last]`，**禁止**只测 computed

6. **F006 硬约束 — Tooltip plugin 测试读真实 wiring**
   - 测试通过 `graphCtorCalls[graphCtorCalls.length - 1].plugins.find(p => p.type === 'tooltip')` 获取真实 plugin 配置
   - 直接调用该配置的 `enable(event, items)` 和 `await getContent(event, items)`
   - **严禁**在测试里手写一个"等价的 enablePredicate"然后只测那个本地变量

### 关键决策（plan/design 已写，但 Executor 最常遗漏）

- **1 跳邻居定义**: `prerequisite_hard` ∪ `prerequisite_soft`（两种 prerequisite 都算，但**不含** `external_hard_refs`——后者走徽标单独表达）
- **Tooltip getContent 必须 async**: G6 v5.1 类型签名是 `Promise<HTMLElement | string>`，写 `async (event, items) => renderPeersHtml(...)`
- **状态命名**: 节点 `faded` / 边 `dimmed` / `emphasized`（Phase 2 未用过 state 机制，G6 保留态 `selected`/`active`/`disabled` 与此无冲突）
- **桥接/对比边**: 明确 **deferred → Phase 3**（不是 resolved，也不做），在 Contract Pack test_debt 已标注
- **renderPeersHtml 纯函数**: null/undefined/{} 输入必须返回 `''`（不崩溃），HTML 特殊字符必须 escape（防注入），模块按字母序排序，同模块内节点按 name 字母序

### 自治边界（autonomy-boundary.md 硬规则）

**Phase 2.5 是视觉任务**。Executor 不得自行声明"视觉验收通过"：

- 实现完成后输出"实现完成，待用户验收"状态
- 列出 design §8 的 3 条验收路径供用户手动操作（浏览器打开 `http://localhost:5273/knowledge-tree`）
- **禁止**输出全绿汇总表或"所有功能已正常"的结论
- 视觉一致性的裁判权在**用户**，不在 Executor
- 测试通过 ≠ 视觉正确（测试不能覆盖 G6 实际渲染的 opacity 值与 tooltip 位置）

### 用户偏好（continued from Phase 2）

- **质量优先**，知识图谱是最关键最核心的内容
- **可视化服务模型**，不独立追求好看；首要用户是教师
- **WSL 优先运行服务进程**，Git Bash 前端 dev 须走 `serve.py`
- **L017 行为变更守卫**: GPT 审查 finding 如果有 `type=behavior_change`，必须单独批准不能批量
- **完成声明铁律**: 跑 `npx vitest run` 出实测结果才能声称实现完成

### 测试命令速查

```bash
# 前端 Phase 2.5 专属测试
cd /c/Users/Administrator/edu-cloud/frontend && npx vitest run src/__tests__/knowledge-tree/ConceptMapPanel.test.js -t "Phase 2.5"

# 前端全量
cd /c/Users/Administrator/edu-cloud/frontend && npx vitest run
# 期望: 17 files / 178 tests PASS

# 后端回归（无后端改动，只确认无巧合破坏）
cd /c/Users/Administrator/edu-cloud && python -m pytest --tb=short -q
```

### 反证验证（Executor 完成实现后必做）

Phase 2.5 R1 因逻辑镜像测试被 FAIL。完成实现后 Executor 必须对每个新增 INV/CE 做 counter-proof：

1. **CE-004**: 临时删掉 `relatedNodeIds` 中 `e.target === focus` 分支 → Task 1 测试 3 应 fail
2. **CE-005**: 临时删掉 `updateElementStates` 的 `!focusedNodeId.value` 清空分支 → Task 2 测试 2 应 fail
3. **CE-007**: 临时把 `relatedEdgeIds` 改回 `props.edges.forEach((e,i)=>...)` 原始索引 → Task 1 测试 6 (dangling edge) 应 fail
4. **CE-008**: 临时删掉 `createGraph` 末尾的 replay 分支 → Task 2 测试 4 应 fail
5. **F006 Tooltip**: 临时改 `plugin.type` 为别的值或删除 `plugin.key` → Task 3 INV-009 wiring 测试应 fail

反证验证通过后恢复源代码，写入审查交接单。

### Gate 2 送审要求

按 plan「自审流程」段：
1. 前端全量 `npx vitest run` → 17 files / 178 tests PASS
2. 5 项反证验证全部执行并记录到审查交接单
3. 写 `docs/plans/2026-04-10-teacher-workbench-phase2.5-review-handoff-batch1.md` 含：
   - 逐 Task 自审表（Task 1-3 状态与 commit hash）
   - 预审自检（5 字段 × 每 slice + 反证命令与输出）
   - 自查四要素（新增文件边界 case / 状态变量异常路径 / 字符串条件判断假阴性）
4. 调用 `codex-review` skill mode=code_review 送审

## 启动 Prompt

```
[edu-cloud] Executor | 2026-04-10 22:03:48
项目: C:\Users\Administrator\edu-cloud
读取 C:\Users\Administrator\edu-cloud\docs\plans\2026-04-10-teacher-workbench-phase2.5-handoff.md，按 C:\Users\Administrator\edu-cloud\docs\plans\2026-04-10-teacher-workbench-phase2.5-plan.md 的 Task 1-3 执行（Phase 2.5 Batch 1：buildVisibleEdgeList helper + relatedNodeIds/relatedEdgeIds computed + G6 state spec + updateElementStates + createGraph 焦点重放 + Tooltip plugin + renderPeersHtml 纯函数）。使用 executing-plans skill。完成后输出审查交接单。使用 codex-review skill 进行 GPT 代码审查。
```
