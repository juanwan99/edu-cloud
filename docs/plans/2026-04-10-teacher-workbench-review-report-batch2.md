[edu-cloud] GPT Reviewer | 2026-04-10 20:18:22 (R1) / 20:33:33 (R2) / 20:43:47 (R3) / 20:51:41 (R4)

## 审查报告: Task 4-6 (Batch 2) — 最终结论 PASS (R4 focused verification)

### 轮次概览

| Round | 时间 | 结论 | 新 findings | 原始日志 SHA256 |
|-------|------|------|------------|----------------|
| R1 | 20:18:22 | FAIL | F-001 HIGH code-bug / F-002 MED code-bug / F-003 HIGH test-gap / F-004 MED test-gap | 6ed5e40dc832afd1f05079e03a30e8ea962fa68d6eadd2f214f45fd8380d2995 |
| R2 | 20:33:33 | FAIL | F-005 MED test-gap（F-001..F-004 全部 verified resolved） | b1fcde8b41ad6c2db31dcfba60872904d1f5391b0165904366c23b486cd27743 |
| R3 | 20:43:47 | FAIL | F-006 MED test-gap（F-005 verified resolved） | 93bc8be553d06be9f27ad3e347f7473d028f4355705b918438c3b8806f112971 |
| R4 | 20:51:41 | **PASS** | 无 new findings（F-006 verified resolved） | a177f5f1769de9724b9a304e6b5da8b8dac3e9d5f0c593a35475ce5efd3b0204 |

**最终结论：PASS** — 所有 6 个 findings 全部 verified resolved，前端 vitest 17 files / 160 tests PASS。

### 轮次 fix 对应 commits

| Round fix | Commit | 内容 |
|-----------|--------|------|
| R1 fix | `2369945` | F-001 教师入口 canEdit / F-002 loadQuality('all') / F-003 mount 测试 / F-004 focus 交互测试 |
| R2 fix | `5fa36da` | F-005 删除过时镜像测试 + TreeNavPanel stub 驱动 select-module('all') 对称分支 |
| R3 fix | `549e298` | F-006 reactive mock auth store + 确定性 ModuleCards 点击 + canEdit=false back-to-overview 负分支 |

### R4 PASS 判定原文摘录

> 结论：PASS
> 本次仅核验 F-006，当前已闭合，且未引入新的 HIGH/MED code-bug 或 test-gap。
> 1. ModuleCards → handleModuleSelect('M1') 现在是确定性测试，不再有条件护栏。
> 2. mock auth store 已能随 roleName 变化让 canEdit 重新计算。
> 3. canEdit=false 的 back-to-overview 负分支现在有真实 mount 测试。
> 4. 旧的 mocked guard 已删除，父级断言现在是实断言。
> 已实际运行 cd frontend && npx vitest run src/__tests__/knowledge-tree/KnowledgeTreePage.mount.test.js，15 tests 全通过。

---

## Round 1 审查报告（历史留档）

结论: **FAIL**

原始 GPT 输出: `docs/plans/.codex-raw-code_review-batch2-r1-20260410-201808.log`
SHA256: `6ed5e40dc832afd1f05079e03a30e8ea962fa68d6eadd2f214f45fd8380d2995`

### 第一段：测试充分性（Test Adequacy）

27/27 Batch 2 tests PASS（ConceptMapPanel 7 + ConceptFocusOverlay 8 + KnowledgeTreePage 12），但 GPT 判定绿灯不足以证明合同满足：
- `KnowledgeTreePage.test.js` 是**逻辑镜像**（用本地 ref/函数重写页面逻辑，未 mount 真实组件）→ F-003 test-gap HIGH
- `ConceptMapPanel.test.js` 未覆盖 Task 5 核心交互（focusedNodeId / clearFocus / onKeyDown / watch(moduleId)） → F-004 test-gap MED

### 第二段：行为正确性（Behavioral Correctness）

**变更理解**：Batch 2 新增 ConceptMapPanel（G6 preset 布局 + BigConcept 分带 + 跨模块徽标）和 ConceptFocusOverlay（焦点模式关系面板），集成到 KnowledgeTreePage 替换 GraphPanel.vue 为 ModuleOverviewPanel/ConceptMapPanel 互斥路由（INV-004），并新增 handleBackToOverview/handleRefreshModule/handleMarkReviewed 三个 handler。init() 新增 loadAllModulesQuality 调用。删除 GraphPanel.vue 实现单一版本纪律。

**对抗性审查**：GPT 在静态核对 + 跑测试后发现两个实际 bug（F-001/F-002），属于逻辑镜像测试掩盖的真实缺陷。GPT 独立 grep `platform_admin` 和 `needsStudentSelector` 定义范围，发现 plan.md:1972 声明 platform_admin 属于教师列但代码 needsStudentSelector 列表不含此角色；GPT 独立追踪 `qualityIssues` 数据源发现 handleBackToOverview 不刷新此 ref 但 RelationReviewPanel 消费它。Executor 自审抽检（INV-005/CE-003）验证通过，但未发现 F-001/F-002（被逻辑镜像测试覆盖盲区掩盖）。

### 第三段：未测试风险（Non-tested Risks）

F-003 的 test-gap 是 F-001/F-002 能在"12 tests PASS"下漏出的**直接原因**。

### 发现清单

#### F-001
- **Severity**: HIGH
- **Category**: code-bug
- **Type**: defect_fix
- **Status**: verified
- **Before-behavior**: 计划 plan.md:1972 要求 `教师 (platform_admin/subject_teacher 等)` 默认直接进入 main-layout（showCards=false）。
- **After-behavior**: `platform_admin` 和 `district_admin` 不在 `needsStudentSelector` 列表中，因此 `init()` 里 `!studentId.value && needsStudentSelector.value` 永远为 false，showCards 保持 true → 停留在 ModuleCards（空的 moduleMastery），拿不到 Phase 2 教师工作台默认入口。
- **Inv-conflict**: direct（直接违反 plan §角色分支要求的教师状态机）
- **Evidence**:
  - `frontend/src/pages/KnowledgeTreePage.vue:119` — `needsStudentSelector = ['subject_teacher', 'homeroom_teacher', 'principal', 'academic_director', 'grade_leader']`（不含 platform_admin/district_admin）
  - `frontend/src/pages/KnowledgeTreePage.vue:132` — `if (!studentId.value && needsStudentSelector.value) showCards.value = false`
  - `frontend/src/config/permissions.js:3` — platform_admin 拥有 edit_knowledge_tree 权限
  - `docs/plans/2026-04-10-teacher-workbench-plan.md:1972` — 教师列明确包含 platform_admin
- **Impact**: Phase 2 教师默认入口对 platform_admin/district_admin 失效，与 plan 状态机不一致，是实际路由行为错误（非文档偏差）。
- **Repair hypothesis**: 不要把"是否默认进教师工作台"绑定到 `needsStudentSelector`，直接基于 `canEdit` 判断（canEdit=true → 直接进 main-layout）。

#### F-002
- **Severity**: MED
- **Category**: code-bug
- **Type**: defect_fix
- **Status**: verified
- **Before-behavior**: 教师从模块图返回 all 视图后，审查工作台（RelationReviewPanel）应对应 all 作用域的质量数据。
- **After-behavior**: `handleBackToOverview()` / `handleModuleSelect('all')` 只刷新 `modulesQuality`（5 模块聚合），不刷新 `qualityIssues`。而 `RelationReviewPanel` 直接消费 `qualityIssues` → 返回 all 后切到 review tab 仍显示上一个模块的质量问题。
- **Inv-conflict**: possible
- **Evidence**:
  - `frontend/src/pages/KnowledgeTreePage.vue:63` — `<RelationReviewPanel :quality-issues="qualityIssues" ...>`
  - `frontend/src/pages/KnowledgeTreePage.vue:148` — `handleModuleSelect(mod)` 只在 `mod !== 'all'` 时调 loadQuality
  - `frontend/src/pages/KnowledgeTreePage.vue:160` — `handleBackToOverview()` 只调 loadAllModulesQuality
  - `frontend/src/components/knowledge-tree/useKnowledgeTree.js:43` — loadQuality(module) 写 qualityIssues
  - `frontend/src/components/knowledge-tree/useKnowledgeTree.js:49` — loadAllModulesQuality() 写 modulesQuality（不同 ref）
- **Impact**: Phase 1 审查工作台在 all 作用域下展示错误的质量问题集合，用户可见的数据作用域回归。
- **Repair hypothesis**: 切回 all 时同步调 `loadQuality('all')`。

#### F-003
- **Severity**: HIGH
- **Category**: test-gap
- **Type**: defect_fix
- **Status**: verified
- **Before-behavior**: KnowledgeTreePage 的关键契约（INV-004 互斥路由 + 角色入口状态机）应由真实页面测试覆盖，错误实现应导致测试 fail。
- **After-behavior**: 当前 `KnowledgeTreePage.test.js` 用本地 `ref`/本地函数重写页面逻辑，没有 import/mount `KnowledgeTreePage.vue`。即使把页面里的真实逻辑改坏，这组测试仍会全部通过（验证：F-001/F-002 是真实 bug，但 12 tests 全绿未能捕获）。
- **Inv-conflict**: direct（INV-004 verification 映射失效）
- **Evidence**:
  - `frontend/src/__tests__/knowledge-tree/KnowledgeTreePage.test.js:8` — 注释明确说"直接测试页面组件需要大量 mock...这里提取并验证关键页面级逻辑"
  - 全文件无 `import KnowledgeTreePage from '../../pages/KnowledgeTreePage.vue'`
  - F-001/F-002 存在但测试全绿 = 反证此 test-gap
- **Impact**: INV-004 verification 映射不可信，逻辑镜像测试（L013 同源）掩盖了 F-001/F-002 两个真实 bug。按 test-gap 判定细则属 HIGH（删除被测函数核心逻辑后测试仍全绿）。
- **Repair hypothesis**: 用 mocked store + composable 挂载真实 `KnowledgeTreePage.vue`，验证 showCards、selectedModule、teacher/admin 角色入口、back-to-overview 后 review tab 数据作用域。

#### F-004
- **Severity**: MED
- **Category**: test-gap
- **Type**: defect_fix
- **Status**: verified
- **Before-behavior**: Task 5 集成行为（ESC 退出 / canvas:click 清焦点 / moduleId 切换清焦点）应由测试保护。
- **After-behavior**: `ConceptMapPanel.test.js` 只覆盖工具栏/band/badge/preset，无用例触发 `focusedNodeId/clearFocus/onKeyDown/watch(moduleId)`。删除这些核心逻辑测试仍全绿。
- **Inv-conflict**: possible
- **Evidence**:
  - `frontend/src/components/knowledge-tree/ConceptMapPanel.vue:189` — `handleNodeClick` / `clearFocus` / `focusPeer`
  - `frontend/src/components/knowledge-tree/ConceptMapPanel.vue:202` — `onKeyDown` (ESC)
  - `frontend/src/components/knowledge-tree/ConceptMapPanel.vue:247` — `graph.on('canvas:click')`
  - `frontend/src/components/knowledge-tree/ConceptMapPanel.vue:274` — `watch(()=>props.moduleId, ()=>{focusedNodeId=null})`
  - `frontend/src/__tests__/knowledge-tree/ConceptMapPanel.test.js` — 7 tests 中无任何焦点交互用例
- **Impact**: Task 5 核心交互无回归保护，handoff 对"15 联测 PASS"充分性描述偏乐观。
- **Repair hypothesis**: 让 G6 mock 记录 `graph.on` 注册的回调，显式测试 node click → overlay / canvas click → 清焦点 / Escape → 清焦点 / moduleId 变化 → 清焦点。

### PASS/FAIL 判定

按 review-templates.md「PASS/FAIL 判定」：code-bug 或 test-gap 的 HIGH/MED 未修复 → FAIL。

本轮 4 条 findings 全部 HIGH/MED 未修复 → **FAIL**，进入 Round 1 修复。

### 行为变更审批记录

本轮 finding 全部 `type=defect_fix`，无 behavior_change，可批量修复。
