---
type: handoff
created: 2026-04-10 19:49:17
project_dir: C:\Users\Administrator\edu-cloud
design: C:\Users\Administrator\edu-cloud\docs\plans\2026-04-10-teacher-workbench-design.md
plan: C:\Users\Administrator\edu-cloud\docs\plans\2026-04-10-teacher-workbench-plan.md
---

# 知识图谱教师工作台 Phase 2 — Batch 2 会话交接卡

## 约束与偏好

**T3 流程**。Phase 2 Batch 1（Tasks 1-3）Gate 2 已 **PASS (R2)**。本卡用于新会话按 plan 执行 Batch 2（Tasks 4-6）。

### 前置状态（只读，不要改动）

- **plan**: `C:\Users\Administrator\edu-cloud\docs\plans\2026-04-10-teacher-workbench-plan.md`（Gate 1 PASS R3 收敛）
- **design**: `C:\Users\Administrator\edu-cloud\docs\plans\2026-04-10-teacher-workbench-design.md`
- **state**: `C:\Users\Administrator\edu-cloud\docs\plans\2026-04-10-teacher-workbench-state.json`（Tasks 1-3 completed, 4-6 pending）
- **gates**: `C:\Users\Administrator\edu-cloud\docs\plans\2026-04-10-teacher-workbench-gates.json`（plan_review: pass, code_review_batch1: pass）
- **Batch 1 R2 PASS 报告**: `C:\Users\Administrator\edu-cloud\docs\plans\2026-04-10-teacher-workbench-review-report-batch1-r2.md`
- **已完成 commits**: `7a5ecfb..d88de1a`（T1-T3 实现 + R1 修复 + R2 审查留档）

### Batch 1 已落盘可供复用

Batch 2 必须建立在以下 Batch 1 产物之上，**直接 import 使用，禁止重实现**：

| 模块 | 绝对路径 | 用途 |
|------|---------|------|
| `computeLayout({nodes, edges, bigConceptOrder})` | `frontend/src/components/knowledge-tree/layoutEngine.js` | ConceptMapPanel 唯一布局来源，G6 `layout.type='preset'` 的坐标输入 |
| `ModuleStatCard.vue` | `frontend/src/components/knowledge-tree/ModuleStatCard.vue` | （Batch 2 不直接用，但 MODULE_COLORS 常量需与之保持一致） |
| `ModuleOverviewPanel.vue` | `frontend/src/components/knowledge-tree/ModuleOverviewPanel.vue` | Task 6 中 `selectedModule='all'` 分支渲染的组件 |
| `modulesQuality` ref + `loadAllModulesQuality()` | `frontend/src/components/knowledge-tree/useKnowledgeTree.js` | Task 6 中为 ModuleOverviewPanel 提供数据 |

### Batch 2 独有陷阱（plan 已写但最易踩坑的点，强调）

1. **INV-005 / Task 4 R1**: ConceptMapPanel 的 G6 `Graph` **必须** `layout: { type: 'preset' }`。节点坐标 100% 由 `computeLayout` 决定，禁止 G6 重排。测试要 assert 此配置。

2. **F002 契约（跨模块徽标）**: `crossModuleBadges` 必须扫 `node.external_hard_refs.out`，**不是** `props.edges`。Phase 1 后端 module 过滤会剥掉跨模块 edge，扫 edges 在生产永远为空。Task 4 测试契约 slice 5 会断言 `vm.crossModuleBadges.B === {M2:2, M3:1}`。

3. **Task 4 defineExpose**: 为让测试访问 `crossModuleBadges` 和 `crossModulePeers`，`<script setup>` 末尾必须 `defineExpose({ crossModuleBadges, crossModulePeers })`。

4. **模式 2 = 方案 C（简化版）**: 单击节点 → 底部浮动 ConceptFocusOverlay + `查看详情` 按钮；**不做节点透明度淡化**（延后 Phase 2.5，design.md 已降级）；**做** `canvas:click` 空白退出 + ESC 键退出。R1 F005 最终处置。

5. **Task 5 集成**: ConceptFocusOverlay 由 ConceptMapPanel 管理显示，键盘监听在 ConceptMapPanel 的 `onMounted/onUnmounted` 生命周期内注册/解除；ESC 关 overlay；canvas 空白 click 关 overlay。**不要**把键盘监听绑在 overlay 自己的 lifecycle 上（overlay 不渲染时监听器丢失）。

6. **Task 6 入口状态机**: 教师（`canEdit=true` 且 `studentId=null`）在 `init()` 中通过 `!studentId.value && needsStudentSelector.value` 自动设 `showCards=false` → 直接进 main-layout + ModuleOverviewPanel；家长/学生 `showCards=true` 保留，点 ModuleCards 才进入 ConceptMapPanel。**不要删除 ModuleCards import**。三条验收路径（教师/家长/学生）都要能跑通。

7. **Task 6 single-version**: 完全 `git rm` 旧 `GraphPanel.vue`，不留注释/fallback/re-export。删除后要 grep 整个 frontend 确认零残留 import（`rg "GraphPanel" frontend/src` 应只剩测试删除确认或完全无匹配）。R1 F001 硬约束。

8. **Task 6 Tab 共存**: Phase 1 的「审查工作台」tab 切换（RelationReviewPanel 等）与本批次必须共存，**不要动 tab 逻辑**。只替换 `.graph-side` 内部。

9. **MODULE_COLORS 一致性**: ConceptMapPanel 使用的模块色必须与 `ModuleStatCard.vue` 一致（M1-M5 五色）。建议从一个常量来源复用，避免双份定义漂移。

### 执行范围与边界

- **本批次不改任何后端代码**。纯 `frontend/` 下。Python 后端仅需确认 0 回归（前次后端测试 1716 passed，3 failed 与本批无关）。
- **不引入新依赖**。继续只用 `@antv/g6 ^5.1.0` 的 `layout: { type: 'preset' }`。
- **Batch 2 完成条件**：Task 4/5/6 各自的「边界条件」「测试契约」「审查清单」全部满足 + `npx vitest run` 前端全绿 + `git rm GraphPanel.vue` + `rg "GraphPanel" frontend/src` 零残留。

### Contract Pack 测试契约（plan §F 已有，不重复）

Batch 2 对应的不变量：
- **INV-004**: `KnowledgeTreePage` graph-side 在 `selectedModule='all'` 时渲染 ModuleOverviewPanel，在 `selectedModule='Mx'` 时渲染 ConceptMapPanel，**互斥**不能同时渲染（Task 6 测试）
- **INV-005**: ConceptMapPanel 的 G6 Graph 配置必须是 `layout: { type: 'preset' }`（Task 4 测试）
- **CE-002**: crossModuleBadges 数据源契约（Task 4 slice 5）
- **CE-003**: 焦点模式退出路径（Task 5 ESC + canvas:click）

### 用户偏好（continued from Batch 1）

- **质量优先**，知识图谱是最关键最核心的内容
- **可视化服务模型**，首要用户是教师（教研/备课/审核）
- **WSL 优先运行服务进程**，Git Bash 前端 dev 须走 `serve.py`
- **完成声明铁律**：必须跑 `npx vitest run` 出实测结果才能声称完成
- **L017 行为变更守卫**：GPT finding 的 `type=behavior_change` 必须单独批准，禁止批量
- **L011 远程日志纪律**：不适用（本批次无 SSH 调试）

### 测试命令速查

```bash
# 前端 Vitest 全量
cd /c/Users/Administrator/edu-cloud/frontend && npx vitest run

# Batch 2 三个新测试文件
cd /c/Users/Administrator/edu-cloud/frontend && npx vitest run \
  src/__tests__/knowledge-tree/ConceptMapPanel.test.js \
  src/__tests__/knowledge-tree/ConceptFocusOverlay.test.js \
  src/__tests__/knowledge-tree/KnowledgeTreePage.test.js

# GraphPanel 残留检查（Task 6 后必跑）
cd /c/Users/Administrator/edu-cloud && rg "GraphPanel" frontend/src

# 后端回归
cd /c/Users/Administrator/edu-cloud && python -m pytest --tb=short -q
```

### 审查送审路径（Gate 2 for Batch 2）

Batch 2 完成后：
1. Executor 输出审查交接单（`docs/plans/2026-04-10-teacher-workbench-review-handoff-batch2.md`）
2. Executor 调用 `codex-review` skill，mode=code_review，送审 commit 范围 Batch 2 的所有 commits
3. GPT 返回结果后按 R1/R2 流程处置 finding

## 启动 Prompt

```
[edu-cloud] Executor | 2026-04-10 19:49:17
项目: C:\Users\Administrator\edu-cloud
读取 C:\Users\Administrator\edu-cloud\docs\plans\2026-04-10-teacher-workbench-batch2-handoff.md，按 C:\Users\Administrator\edu-cloud\docs\plans\2026-04-10-teacher-workbench-plan.md 的 Task 4-6 执行（Batch 2：ConceptMapPanel + ConceptFocusOverlay + KnowledgeTreePage 集成 + git rm GraphPanel.vue）。使用 executing-plans skill。完成后输出审查交接单。使用 codex-review skill 进行 GPT 代码审查。
```
