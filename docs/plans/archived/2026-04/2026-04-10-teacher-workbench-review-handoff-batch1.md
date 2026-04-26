[edu-cloud] Executor→Reviewer | 2026-04-10 19:13:49

## 审查交接单: Task 1-3（Batch 1：基础算法与概览面板）

计划: `C:/Users/Administrator/edu-cloud/docs/plans/2026-04-10-teacher-workbench-plan.md`
设计: `C:/Users/Administrator/edu-cloud/docs/plans/2026-04-10-teacher-workbench-design.md`

### 逐 Task 自审

| Task | 计划要求 | 实际执行 | 状态 | 说明 |
|------|---------|---------|------|------|
| T1 | layoutEngine.js toposort + BigConcept band layout + 8 tests | commit `7a5ecfb`, layoutEngine.js 新增（≈160 行）+ layoutEngine.test.js 新增（8 tests），8/8 PASS | 🔀 | 计划文本写"Expected: 9 tests PASS"但计划内嵌测试代码只有 8 个 `it()`。实现按代码走（8 tests）。另：实现对 plan 示例做了 2 处确定性加固 —— ① 环节点回退 rank 用 `Math.max(...rank.values())+1` 替代 plan 的 `Math.max(0, ...) + 1`（当 rank 非空时语义一致，空时零节点短路已兜底，不影响测试）；② band 内 rank 遍历从 `Map.entries()` 改为对 key 数字排序后遍历（确保同 band 多 rank 时 X 坐标分配顺序确定，超出 plan 的字母排序保证） |
| T2 | ModuleStatCard.vue 单模块卡片 + 5 tests | commit `16ed04f`, ModuleStatCard.vue 新增（≈120 行）+ ModuleStatCard.test.js 新增（5 tests），5/5 PASS | ✅ | 与计划一致 |
| T3 | ModuleOverviewPanel.vue + useKnowledgeTree.loadAllModulesQuality + 4+2 tests | commit `4bd3733`, ModuleOverviewPanel.vue 新增（≈140 行）+ ModuleOverviewPanel.test.js 新增（4 tests）+ useKnowledgeTree.js 扩展 modulesQuality/loadAllModulesQuality + useKnowledgeTree.test.js 追加 2 tests，6/6 PASS | 🔀 | modulesData computed 对 `mod.big_concepts`/`bc.concept_ids` 做了 `\|\| []` 防御，plan 没写（plan 的 mock 数据保证这些字段存在，但运行时可能缺失）。这是防御性加固不是功能偏离 |

> 状态: ✅一致 / ❌不一致 / 🔀改进（实现优于计划）

### 预审自检（送审前必填）

| 测试契约 slice | 对应测试文件:函数 | 验证命令 | 实际输出 | 反证验证 |
|---------------|------------------|---------|---------|---------|
| T1-1 toposort 对硬 DAG 返回正确 rank | `layoutEngine.test.js > toposort rank > linear chain A→B→C` | `cd frontend && npx vitest run src/__tests__/knowledge-tree/layoutEngine.test.js` | 8 passed | 如果实现把所有 rank 设为 0，`positions.B.x > positions.A.x` 会失败（B 与 A 将同 X） |
| T1-2 determinism | `layoutEngine.test.js > determinism > same input produces identical output` | 同上 | 8 passed | 如果改为 `Array.from(Set)` 不排序，跨 JS 引擎迭代顺序不稳，`r1 !== r2`；已用 `[...nodeIds].sort()` |
| T1-3 band 约束 | `layoutEngine.test.js > band layout > nodes of same BigConcept fall within their band Y range` | 同上 | 8 passed | 如果让 rank bucket 内多节点 Y spread 超出 band，断言 `A.y <= bc1Band.yMax` 失败；已用 `availableVerticalSpread = Math.min(bandHeight * 0.7, NODE_HEIGHT * 3)` 限制 |
| T1-4 环降级 | `layoutEngine.test.js > cycle handling > cycle does not crash` | 同上 | 8 passed | 如果 toposort 不检测未访问节点，`positions.A` 为 undefined；已通过 `cyclicNodes.filter(n => !rank.has(n.id))` 回填 |
| T2-1 renders | `ModuleStatCard.test.js > renders module name, counts, and progress` | `cd frontend && npx vitest run src/__tests__/knowledge-tree/ModuleStatCard.test.js` | 5 passed | 如果把 conceptCount 和 bigConceptCount 显示反（22↔3），用 12/22 = 55% 断言无法满足 |
| T2-2 click emit | `ModuleStatCard.test.js > emits select on click` | 同上 | 5 passed | 如果 emit 名错为 `selected`，`emitted('select')` 为 undefined |
| T2-3 badges 条件渲染 | `ModuleStatCard.test.js > renders HIGH/MED badges only when counts > 0` | 同上 | 5 passed | 如果永远渲染 badges（不判空），`none.text().not.toContain('HIGH')` 会失败 |
| T3-1 5 cards | `ModuleOverviewPanel.test.js > renders one card per navigation module` | `cd frontend && npx vitest run src/__tests__/knowledge-tree/ModuleOverviewPanel.test.js` | 4 passed | 如果只渲染 modulesQuality 中存在的模块（而非 navigation），mockNavigation 传 2 卡但 modulesQuality={} 会渲染 0 卡 |
| T3-2 select-module emit | `ModuleOverviewPanel.test.js > emits select-module on card click` | 同上 | 4 passed | 如果 ModuleStatCard 的 @select 没被正确转发，`emitted('select-module')` 为 undefined |
| T3-3 cross-module aggregation | `ModuleOverviewPanel.test.js > aggregates cross-module hard prerequisite links` | 同上 | 4 passed | 如果把同模块边也算进 crossModuleLinks（缺 `srcMod === tgtMod continue`），会出现 `M1 → M1` |
| T3-4 Promise.allSettled | `useKnowledgeTree.test.js > loadAllModulesQuality tolerates partial failures` | `cd frontend && npx vitest run src/__tests__/knowledge-tree/useKnowledgeTree.test.js -t loadAllModulesQuality` | 2 passed | 如果用 `Promise.all`，任一 reject 会抛到顶层，modulesQuality 仍是初始 `{}`；已用 `Promise.allSettled` |
| T3-5 M1-M5 并发调用 5 次 | `useKnowledgeTree.test.js > loadAllModulesQuality calls qualityCheck for M1-M5` | 同上 | 2 passed | 如果串行 await，`qualityCheck.mock.calls` 仍为 5 但会测 order；这条只断次数 + 参数集 |

**全量回归：** `cd frontend && npx vitest run` → **14 files, 120 tests PASS**（新增 19 tests：8+5+2+4，其余 101 保持绿色，无回归）

### 验证清单自检（Task 1）

- ✓ computeLayout 是纯函数（无副作用、无随机、无全局状态） — 实现未引用 Math.random/Date.now/任何外部变量，只读 props
- ✓ 两次同输入返回完全相同的 positions 和 bands — `determinism` 测试断言 `r1.positions === r2.positions` 深度相等 PASS
- ✓ toposort 排序使用 id 字母序 — Line 49 `const sortedIds = [...nodeIds].sort()` + Line 60 `adj.get(u).slice().sort()`
- ✓ 环节点降级为 rank+1 平铺，不抛异常 — `cyclicNodes.length > 0` 分支回填 fallbackRank，warnings push `cycle_detected`
- ✗ 内部使用 Math.random 或 Date.now — grep 确认无
- ✗ 节点集合用 Set 遍历 — 所有 Set 都先 `[...set].sort()` 或先转 Array 再 sort

### 验证清单自检（Task 2）

- ✓ 单一职责：纯展示组件 — 无 axios/fetch/store 导入
- ✓ click 事件通过 emit('select') 向上传递 — `@click="$emit('select')"`
- ✓ MODULE_COLORS 常量与 Phase 1 GraphPanel 一致 — M1~M5 颜色码与 plan 内嵌常量一致
- ✓ reviewPercent 在 conceptCount=0 时返回 0 — `if (props.conceptCount === 0) return 0`
- ✗ 组件内部直接调用 API — 确认无
- ✗ 样式写死颜色导致无法通过 props 主题化 — 颜色通过 `:style` 绑定 moduleColor computed

### 验证清单自检（Task 3）

- ✓ 卡片数据从 navigation + nodes 聚合计算 — `modulesData` computed
- ✓ 跨模块关系从 edges 聚合（排除同模块）— `if (!srcMod || !tgtMod || srcMod === tgtMod) continue`
- ✓ loadAllModulesQuality 用 Promise.allSettled — `useKnowledgeTree.js:50`
- ✓ select-module 事件 payload 是 module id 字符串 — `@select="$emit('select-module', mod.id)"`
- ✗ 组件内直接调 API — 确认无（quality 数据从 props.modulesQuality 进来）
- ✗ 跨模块聚合用对象而非 Map — 用 `Map` 聚合 `counts`，最后 toSorted 输出数组

### 根因分析

非 bug fix，跳过。

### 自查（四要素格式）

- **新增文件的边界 case**：
  构造输入: layoutEngine 空 nodes 输入
  运行命令: `cd frontend && npx vitest run src/__tests__/knowledge-tree/layoutEngine.test.js -t "empty nodes"`
  实际输出:
  ```
  ✓ layoutEngine > toposort rank > empty nodes returns empty positions
    Test Files  1 passed (1)
    Tests       1 passed | 7 skipped (8)
  ```
  结论: 空数组早 return，`positions={}, bands={}` 符合边界契约

- **状态变量/锁的异常路径**：
  构造输入: loadAllModulesQuality 部分模块 API reject
  运行命令: `cd frontend && npx vitest run src/__tests__/knowledge-tree/useKnowledgeTree.test.js -t "tolerates partial"`
  实际输出:
  ```
  ✓ useKnowledgeTree > loadAllModulesQuality tolerates partial failures
    Test Files  1 passed (1)
    Tests       1 passed | 6 skipped (7)
  ```
  结论: Promise.allSettled 捕获 reject，失败模块填 `{highCount:0, medCount:0}`，状态变量 `modulesQuality` 不会停在 undefined

- **字符串匹配/条件判断的假阴性**：
  构造输入: ModuleStatCard highCount=0, medCount=0（不应渲染 badges）
  运行命令: `cd frontend && npx vitest run src/__tests__/knowledge-tree/ModuleStatCard.test.js -t badges`
  实际输出:
  ```
  ✓ ModuleStatCard > renders HIGH/MED badges only when counts > 0
    Test Files  1 passed (1)
    Tests       1 passed | 4 skipped (5)
  ```
  结论: `v-if="highCount > 0 || medCount > 0"` 双零时不渲染，断言 `.not.toContain('HIGH')` PASS

### 语义回归自检

semantic_risk=false（Batch 1 都是新增文件，不改变已有运行时行为；useKnowledgeTree.js 仅追加 state 和函数，现有 5 个用例依然 PASS），跳过。

### 送审对象

- **本次审查范围** 仅 Task 1-3 新增/修改的 5 个文件 + 2 个测试文件
- **送审 commits** `7a5ecfb` / `16ed04f` / `4bd3733`（state.json 的 `19fc5b9` 是 housekeeping，不需要审）
- **Contract Pack 相关不变量**：
  - INV-001（纯函数 `{positions, bands, warnings}` 全量稳定）：**R1 补强**由 `layoutEngine.test.js > determinism > non-trivial layout is deterministic across positions, bands, and warnings` 和 `cyclic input determinism includes warnings field` 两个测试联合覆盖（原 R0 测试仅比较 positions/bands，未满足 INV-001 定义，F001 已修复）
  - INV-002（X 递增）：由 `toposort rank > linear chain A→B→C` 测试覆盖
  - INV-003（Y band 约束）：由 `band layout > nodes of same BigConcept fall within their band Y range` 测试覆盖
  - INV-004（KnowledgeTreePage 互斥渲染）、INV-005（G6 preset）：属 Batch 2

### 不审查范围（避免越权）

- Task 4-6（ConceptMapPanel / ConceptFocusOverlay / KnowledgeTreePage 集成）属 Batch 2
- KnowledgeTreePage.vue 现有修改来自之前会话（git status 已标 M），与本批次无关
- Phase 1 审查工作台（RelationReviewPanel 等）本批未动

### 下一步

使用 codex-review skill 对 Batch 1（Tasks 1-3）进行 GPT Code Review (Gate 2)。
