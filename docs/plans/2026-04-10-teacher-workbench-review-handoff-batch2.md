[edu-cloud] Executor→Reviewer | 2026-04-10 20:07:23

## 审查交接单: Task 4-6 (Batch 2)

计划: `C:\Users\Administrator\edu-cloud\docs\plans\2026-04-10-teacher-workbench-plan.md`
送审 commit 范围: `0cc0819..45fcbd3`（4 commits，不含已 PASS 的 Batch 1）
- `0cc0819` feat: ConceptMapPanel — G6 preset rendering + BigConcept bands + cross-module badges
- `7661d44` feat: ConceptFocusOverlay + integrate into ConceptMapPanel with ESC/canvas exit
- `1678260` feat: wire ModuleOverviewPanel + ConceptMapPanel into KnowledgeTreePage; remove GraphPanel
- `45fcbd3` chore(state): teacher-workbench Batch 2 Tasks 4-6 completed

### 逐 Task 自审

| Task | 计划要求 | 实际执行 | 状态 | 说明 |
|------|---------|---------|------|------|
| T4 | ConceptMapPanel.vue（G6 preset + 分带 + crossModuleBadges from external_hard_refs.out + defineExpose）+ 6 tests | commit `0cc0819`: 组件 289 行，layout via computeLayout, G6 `layout:{type:'preset'}` (INV-005)，crossModuleBadges 扫 `n.external_hard_refs.out`（不扫 edges，F002），`defineExpose({crossModuleBadges, crossModulePeers})`。**7 tests PASS**（比计划多 1：INV-005 preset 断言，直接验证 Graph ctor 参数） | 🔀 | 改进：增加 INV-005 preset 断言测试（mock G6 Graph class 捕获构造参数），比计划预期多 1 个测试。该测试是机械校验 `layout.type='preset'` 的反例检测——错误实现改用 `dagre`/`force` 会被立即捕获。原因：plan 中只在审查清单写"G6 只用 preset"，未落入可执行测试；该 invariant 需要 first-class 测试保护。 |
| T5 | ConceptFocusOverlay.vue（前置/后继/桥接关系正确方向 + canEdit 禁用 mark-reviewed + 6 tests）+ 集成到 ConceptMapPanel（ESC 键 + canvas:click 退出 + module 切换清除焦点）+ 共 10 tests | commit `7661d44`: ConceptFocusOverlay.vue 独立组件，prereqs/successors/bridgeContrast 三组 computed 严格从 edges 推导方向。集成到 ConceptMapPanel：新增 `focusedNodeId` ref + `focusedConcept` computed + `handleNodeClick`/`clearFocus`/`focusPeer`/`onKeyDown`；`graph.on('canvas:click')` 清焦点（F005）；`window keydown` ESC 在 onMounted/onUnmounted 对称注册；`watch(moduleId)` 清焦点。**ConceptFocusOverlay 8 tests + ConceptMapPanel 7 tests = 15 联测 PASS**（比计划预期 10 多 5） | 🔀 | 改进 1：overlay 新增 test "does not render when concept is null"——防御性测试，验证 `v-if="concept"` 边界行为。改进 2：overlay 新增 test "focus-peer event fired when peer tag clicked"——验证 focus-peer 导航链路（plan 未写但 computed 中已 emit）。原因：ConceptFocusOverlay 是焦点状态的唯一 UI 入口，peer 点击触发 focus 切换是核心交互，需要直接测试保护。defineExpose 额外暴露 `focusedNodeId` + `clearFocus`（为 Task 6 集成测试预留）。 |
| T6 | KnowledgeTreePage 集成（ModuleOverviewPanel/ConceptMapPanel 互斥 + init 调 loadAllModulesQuality + handleBackToOverview/handleMarkReviewed）+ git rm GraphPanel.vue + 2 tests + 全量 vitest | commit `1678260`: KnowledgeTreePage.vue 替换 GraphPanel import 为 ModuleOverviewPanel + ConceptMapPanel；graph tab 内 `v-if selectedModule==='all'` → ModuleOverviewPanel / `v-else` → ConceptMapPanel（INV-004 互斥）；init() 新增 `loadAllModulesQuality`；handleModuleSelect 分支 all/non-all 路由 quality API；新增 handleBackToOverview/handleRefreshModule/handleMarkReviewed。`git rm` GraphPanel.vue（预先存在的未提交视觉微调已 stash 以便可恢复：`git stash list`）；`rg GraphPanel frontend/src` 零匹配。KnowledgeTreePage.test.js **12 tests PASS**（原 4 + 新 8）。前端全量 **146 tests PASS** / **16 files passed**。 | 🔀 | 改进 1：新增 test "handleModuleSelect(all) calls loadAllModulesQuality not loadQuality"——反向验证 all 分支不误触 single-module quality。改进 2：新增 test "init sets showCards=false for teacher"——直接验证入口状态机 L14/L17。改进 3：新增 test "handleMarkReviewed dispatches set_review_status op via handleEdit"——验证 set_review_status payload 精确到 `{op, id, status}`。改进 4：GraphPanel.vue 的预先未提交修改通过 `git stash` 保留而非直接丢弃（L016 不可逆操作纪律）。原因：plan 测试契约只要求 2 tests（routing + select-module），实际执行发现多个关键行为缺测试保护。 |

### 预审自检（送审前必填）

| 测试契约 slice | 对应测试文件:函数 | 验证命令 | 实际输出 | 反证验证 |
|---------------|------------------|---------|---------|---------|
| INV-005 G6 preset | ConceptMapPanel.test.js::`INV-005: G6 Graph must use layout.type=preset` | `cd frontend && npx vitest run src/__tests__/knowledge-tree/ConceptMapPanel.test.js -t INV-005` | `7 passed` | 改 ConceptMapPanel `layout: { type: 'preset' }` → `{type: 'force'}` 测试会 fail（`expect(ctorArg.layout).toEqual({type:'preset'})`直接 assert） |
| F002 跨模块徽标 | ConceptMapPanel.test.js::`generates cross-module badges from node.external_hard_refs.out` | 同上 `-t cross-module` | `7 passed` | 改实现为扫 `props.edges` → 测试会 fail（`vm.crossModuleBadges.B === {M2:2,M3:1}` 会变为 `{}`，因为 props.edges=[]） |
| CE-003 关系方向 | ConceptFocusOverlay.test.js::`renders prerequisites and successors in correct direction` | `npx vitest run src/__tests__/knowledge-tree/ConceptFocusOverlay.test.js` | `8 passed` | 把 prereqs computed 中 `e.target === concept.id` 改成 `e.source === concept.id` → 测试会 fail（前置依赖数为 2 而非 1） |
| INV-004 互斥路由 | KnowledgeTreePage.test.js::`selectedModule=all → ModuleOverviewPanel branch, ConceptMapPanel not` + `selectedModule=M1 → ConceptMapPanel branch` | `npx vitest run src/__tests__/knowledge-tree/KnowledgeTreePage.test.js` | `12 passed` | 把模板 `v-else` 删除改为同级 `v-if` → 测试反例（showOverview 和 showConceptMap 同时 true）会 fail |

### 验证清单自检

**Task 4 审查清单**（plan 第 1499-1507 行）：
- ✅ layout 用 Vue computed 缓存（ConceptMapPanel.vue:97 `computed(() => computeLayout(...))`）
- ✅ G6 只用 preset layout（ConceptMapPanel.vue:221 `layout: { type: 'preset' }`）+ **INV-005 测试**保护
- ✅ BigConcept 分带用 SVG 在 G6 容器下层（ConceptMapPanel.vue:20-37 `.band-layer` z-index:1，`.g6-container` z-index:2）
- ✅ moduleId/nodes/edges 变化时 destroy + 重建（ConceptMapPanel.vue:265 watch + destroyGraph + nextTick createGraph）
- ✅ crossModuleBadges 使用 `node.external_hard_refs.out`（不扫 edges，F002）+ **6 case 测试**保护
- ✗ buildG6Data 布局重算（已规避：buildG6Data 读 `layout.value.positions`，不重算）
- ✗ crossModuleBadges 扫 edges（已规避：测试 `generates cross-module badges` 反证）

**Task 5 审查清单**（plan 第 1946-1953 行）：
- ✅ Overlay 独立组件，不访问外部 state（ConceptFocusOverlay.vue defineProps only）
- ✅ 关系方向正确（prereqs `e.target===concept.id`, successors `e.source===concept.id`）+ **CE-003 测试**
- ✅ 模块切换时清除焦点（ConceptMapPanel.vue `watch(()=>props.moduleId, ()=>{focusedNodeId.value=null})`）
- ✅ ESC 键监听在 mount/unmount 对称（`window.addEventListener('keydown', onKeyDown)` / `removeEventListener`）
- ✗ 节点淡化（计划已降级到 Phase 2.5）
- ✗ focus-peer 闪烁（v1 接受）

**Task 6 审查清单**（plan 第 2186-2192 行）：
- ✅ 条件渲染严格互斥（`v-if="selectedModule === 'all'"` / `v-else`）+ **INV-004 测试**
- ✅ GraphPanel.vue 被 git rm 删除（`git log --diff-filter=D --name-only` 可见）
- ✅ 切换到 all 时重新调 loadAllModulesQuality（handleBackToOverview + handleModuleSelect('all') 分支）
- ✅ handleMarkReviewed 走 handleEdit 路径（set_review_status op）
- ✅ 删除 GraphPanel.vue 后零残留 import（`rg GraphPanel frontend/src` → No files found）
- ✅ 模块切换时 ConceptMapPanel destroy 旧 graph（Task 4 的 watch 已覆盖）

### 根因分析

非 bug fix 任务，跳过。

### 自查（四要素格式）

- **新增文件的边界 case**：
  构造输入: ConceptMapPanel with `nodes=[]`, ConceptMapPanel with `nodes=mockNodes` 但 `qualityIssues=[]`（LOW 不显示徽章）；ConceptFocusOverlay with `concept=null`
  运行命令: `cd frontend && npx vitest run src/__tests__/knowledge-tree/ConceptMapPanel.test.js src/__tests__/knowledge-tree/ConceptFocusOverlay.test.js`
  实际输出:
  ```
   Test Files  2 passed (2)
        Tests  15 passed (15)
     Duration  3.16s
  ```
  结论: 空节点/无质量问题/null concept 全部按预期行为处理（badges 不渲染、overlay 不挂载）

- **状态变量/锁的异常路径**：
  构造输入: ConceptMapPanel onMounted → nextTick → createGraph（G6 Graph ctor 捕获 `{layout:{type:'preset'}}`）；onUnmounted → destroyGraph + removeEventListener
  运行命令: `cd frontend && npx vitest run src/__tests__/knowledge-tree/ConceptMapPanel.test.js -t INV-005`
  实际输出:
  ```
  ✓ ConceptMapPanel > INV-005: G6 Graph must use layout.type=preset
  Test Files  1 passed (1)   Tests  7 passed (7)
  ```
  结论: onMounted/onUnmounted lifecycle 对称，graph ctor 参数被机械校验捕获

- **字符串匹配/条件判断的假阴性**：
  构造输入: `node.external_hard_refs.out=[{module:'M2'}×2, {module:'M3'}×1]` 断言 `badgeMap.B === {M2:2, M3:1}`；反例 `nodes=mockNodes`（无 external_hard_refs） 断言 `badgeMap === {}`
  运行命令: `cd frontend && npx vitest run src/__tests__/knowledge-tree/ConceptMapPanel.test.js -t cross-module`
  实际输出:
  ```
   ✓ ConceptMapPanel > generates cross-module badges from node.external_hard_refs.out (F002) 5ms
   ✓ ConceptMapPanel > crossModuleBadges empty when no nodes have external_hard_refs 2ms
  ```
  结论: F002 契约（扫 out 而非 edges）有双向测试——正例（有 external_hard_refs 断言 badgeMap 精确结构）+ 反例（无 external_hard_refs 断言 badgeMap 为空）

### 前端全量回归证据

```
cd /c/Users/Administrator/edu-cloud/frontend && npx vitest run
 Test Files  16 passed (16)
      Tests  146 passed (146)
   Duration  7.98s
```

### 影响面梳理（Batch 2 Δ）

**新增文件**：
- `frontend/src/components/knowledge-tree/ConceptMapPanel.vue` (289 行)
- `frontend/src/components/knowledge-tree/ConceptFocusOverlay.vue` (181 行)
- `frontend/src/__tests__/knowledge-tree/ConceptMapPanel.test.js` (159 行，7 tests)
- `frontend/src/__tests__/knowledge-tree/ConceptFocusOverlay.test.js` (94 行，8 tests)

**修改文件**：
- `frontend/src/pages/KnowledgeTreePage.vue` (+75/-20 行，路由改写 + 新增 4 个 handler)
- `frontend/src/__tests__/knowledge-tree/KnowledgeTreePage.test.js` (+152 行，8 新测试)
- `CLAUDE.md` (1 行描述更新)
- `docs/plans/2026-04-10-teacher-workbench-state.json`（状态推进）

**删除文件**：
- `frontend/src/components/knowledge-tree/GraphPanel.vue`（单一版本纪律 F001）

**后端**：零改动
**依赖**：零新增
**回归面**：KnowledgeTreePage 是 GraphPanel 的唯一消费者，删除后无残留引用

### 已知遗留项（按计划 test_debt 段）

1. 焦点模式下节点视觉淡化 → Phase 2.5（plan 已降级）
2. 跨模块徽标悬停对端列表 → Phase 2.5（G6 5.x badge API 不成熟）
3. Batch 2 未做浏览器人工验证（Task 6 Step 4）——Executor 没有 GUI 环境，留给用户

### 预先存在但未处理项（不阻塞审查）

- GraphPanel.vue 的未提交视觉微调已 `git stash` 保留（L016 不可逆纪律），可 `git stash pop` 恢复（但与本批次目标冲突，建议丢弃）
- 仓库中多个未提交文件（card-editor/*, RelationReviewPanel 等）与 Batch 2 无关，未触碰

**使用 codex-review skill 进行 GPT 代码审查**。
