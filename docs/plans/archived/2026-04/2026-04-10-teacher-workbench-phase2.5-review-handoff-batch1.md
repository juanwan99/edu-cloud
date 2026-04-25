[edu-cloud] Executor→Reviewer | 2026-04-10 22:22:42

## 审查交接单: Task 1-3 (Phase 2.5 Batch 1)

计划: `C:\Users\Administrator\edu-cloud\docs\plans\2026-04-10-teacher-workbench-phase2.5-plan.md`
设计: `C:\Users\Administrator\edu-cloud\docs\plans\2026-04-10-teacher-workbench-phase2.5-design.md`
交接卡: `C:\Users\Administrator\edu-cloud\docs\plans\2026-04-10-teacher-workbench-phase2.5-handoff.md`
Gate 1 Plan Review 报告: `docs/plans/2026-04-10-teacher-workbench-phase2.5-plan-review-report.md`（R2 PASS）

**Batch 1 commit**: `b909ccf feat(knowledge-tree): Phase 2.5 Batch 1 — 焦点淡化 + 徽标 Tooltip (T1-T3)`
**改动文件**（与 plan 声明范围一致）：
- `frontend/src/components/knowledge-tree/ConceptMapPanel.vue`（+176 行 / -10 行）
- `frontend/src/__tests__/knowledge-tree/ConceptMapPanel.test.js`（+416 行）
- `CLAUDE.md`（+1 行 / -1 行，doc_sync_guard 触发的同步）
总计 583 insertions(+) / 11 deletions(-)，约 172 有效代码 LOC（不含测试与文档）。

### 逐 Task 自审

| Task | 计划要求 | 实际执行 | 状态 | 说明 |
|------|---------|---------|------|------|
| T1 | buildVisibleEdgeList helper + relatedNodeIds/relatedEdgeIds computed + 改造 buildG6Data 共用 helper + 扩展 defineExpose + 7 tests (INV-006 + CE-004 + F003 dangling + non-prerequisite 过滤) | ConceptMapPanel.vue L159 helper / L175 relatedNodeIds / L189 relatedEdgeIds / buildG6Data L213 改用 helper；defineExpose 增量扩展 relatedNodeIds/relatedEdgeIds。test.js 新增 describe 'Phase 2.5 INV-006' 7 个测试。commit b909ccf 一次性落盘 | ✅ | 严格按 plan Task 1 代码块落地；helper 过滤规则保持与 Phase 2 原 buildG6Data 语义等价（`visibleNodeIds = new Set(props.nodes.map(n => n.id))`） |
| T2 | G6 node.state.faded + edge.state.dimmed/emphasized spec + updateElementStates 函数 + watch(focusedNodeId,...) + createGraph 末尾重放 + G6 mock 扩展 setElementState spy + 4 tests (INV-007/INV-008 + CE-005 + F004 rebuild) | ConceptMapPanel.vue L283 node.state / L304 edge.state / L352 updateElementStates / L422 watch(focusedNodeId,...) / L343 createGraph 末尾 nextTick(updateElementStates)。test.js L18 G6 mock 加 `this.setElementState = vi.fn().mockResolvedValue(undefined)`；新增 describe 'Phase 2.5 INV-007/INV-008' 4 个测试 | ✅ | F001 严守（watch 组件内部 ref）/ F003 严守（updateElementStates 用 helper 拿 visibleId）/ F004 严守（createGraph 末尾 replay）/ F005 严守（真实 spy 断言） |
| T3 | Tooltip plugin（type=tooltip / key=badge-tooltip / trigger=hover / enable 谓词 / async getContent）+ renderPeersHtml 纯函数 + escapeHtml + 扩展 defineExpose + 8 tests (INV-009/INV-010 + CE-006) | ConceptMapPanel.vue L306 plugins 配置 / L381 renderPeersHtml / L394 escapeHtml；test.js 新增 describe 'Phase 2.5 INV-009/INV-010 + CE-006' 8 个测试（INV-010 content / INV-010 determinism / CE-006 null-empty / CE-006 escape / INV-009 wiring / INV-009 enable / INV-009 getContent / INV-009 getContent empty）| 🔀 | **改进**：测试数 8（plan Task 3 列举 8 测试但期望汇总 "178 tests"，实际为 19 新增=179 tests）。我严格按 plan Task 3 的 8 测试清单落地；与 handoff §Gate 2 送审要求"Phase 2.5 的 18"不完全对齐（多 1 测试），属于 +1 质量改进，无功能偏离 |

状态: ✅ 一致 / ❌ 不一致 / 🔀 改进（多 1 个 INV-009 getContent empty 测试，plan Task 3 测试契约明列；汇总估算 18 为估算误差）

### 预审自检（送审必填）

| 测试契约 slice | 对应测试文件:函数 | 验证命令 | 实际输出 | 反证验证 |
|---------------|------------------|---------|---------|---------|
| INV-006 #1 null 时空 Set | ConceptMapPanel.test.js :: "relatedNodeIds is empty Set when focusedNodeId is null (initial state)" | `npx vitest run src/__tests__/knowledge-tree/ConceptMapPanel.test.js -t "Phase 2.5 INV-006"` | PASS (7/7) | 无需反证（空态语义由 `if (!focus) return new Set()` 兜底，CE-004 已反证验证 source/target 双向） |
| INV-006 #2/3 双向邻居 CE-004 | ConceptMapPanel.test.js :: "relatedNodeIds includes focus self + predecessors + successors (hard and soft) — CE-004 guard" | 同上 | PASS | **反证 1 CE-004**：删除 `if (e.target === focus) related.add(e.source)` 分支 → `expected false to be true` at line 399 `expect(r.has('A')).toBe(true)` → 精确 fail（focus=B 时反向边 A→B 下 A 丢失）→ 恢复后再跑 PASS |
| INV-006 #6 F003 dangling edge | ConceptMapPanel.test.js :: "F003 guard: buildVisibleEdgeList skips edges whose endpoint is filtered out, keeping id alignment" | 同上 | PASS | **反证 3 CE-007**：把 relatedEdgeIds 改回 `props.edges.forEach((e,i) => ... id: edge-${i})` 原始索引 → `expected false to be true` at line 442 `expect(has('edge-1')).toBe(true)` → 精确 fail（dangling 边占用 edge-1，B→C 被错认 edge-2）→ 恢复后再跑 PASS |
| INV-007 精确 state map | ConceptMapPanel.test.js :: "INV-007: entering focus triggers graph.setElementState with precise state map" | `npx vitest run src/__tests__/knowledge-tree/ConceptMapPanel.test.js -t "Phase 2.5 INV-007"` | PASS (4/4) | （反证 CE-004 间接覆盖：source/target 双向错了后 state map 的 A/D 分类会偏，该测试也 fail） |
| INV-008 + CE-005 清空 | ConceptMapPanel.test.js :: "INV-008 + CE-005: clearFocus triggers graph.setElementState({}, true)" | 同上 | PASS | **反证 2 CE-005**：删除 updateElementStates 的 `if (!focusedNodeId.value) { try { graph.setElementState({}, true) }; return }` 清空分支 → `expected 1 to be greater than 1` at line 506 → 精确 fail（clearFocus 后 spy 次数未增长）→ 恢复后再跑 PASS |
| F004 graph rebuild | ConceptMapPanel.test.js :: "F004 graph rebuild: createGraph replays focus state after destroy/create cycle" | 同上 | PASS | **反证 4 CE-008**：删除 createGraph 末尾 `if (focusedNodeId.value) { nextTick(updateElementStates) }` → `expected 0 to be greater than 0` at line 551 → 精确 fail（新 graph 实例 spy calls=0）→ 恢复后再跑 PASS |
| INV-009 wiring (F006) | ConceptMapPanel.test.js :: "INV-009: Tooltip plugin is wired to Graph with correct type/key/trigger" | `npx vitest run src/__tests__/knowledge-tree/ConceptMapPanel.test.js -t "Phase 2.5 INV-009"` | PASS (4/4) | **反证 5 F006**：把 `type: 'tooltip'` 改为 `type: 'bogus-type'` → `expected undefined to be defined` at line 646 → 精确 fail（`cfg.plugins.find(p => p.type === 'tooltip')` 返回 undefined）→ 恢复后再跑 PASS |
| INV-010 determinism | ConceptMapPanel.test.js :: "INV-010 determinism: module entries sorted alphabetically" | 同上 | PASS | 未单独反证——determinism 测试本身通过构造 M3→M2 输入验证字母序 |
| CE-006 null/{}/empty | ConceptMapPanel.test.js :: "CE-006: renderPeersHtml returns empty string for null / undefined / {} / empty arrays" | 同上 | PASS | 未单独反证——退化输入语义由 `if (!peers \|\| typeof peers !== 'object') return ''` + `entries.filter(([, list]) => Array.isArray(list) && list.length > 0)` 双层保障，4 项输入逐个断言 |
| CE-006 HTML escape | ConceptMapPanel.test.js :: "CE-006: renderPeersHtml escapes HTML in module id and node name" | 同上 | PASS | 断言同时检查 `not.toContain('<script>...)` 和 `toContain('&lt;script&gt;')` 双向 |

**反证验证汇总（5/5）**：全部精确 fail，破坏源代码对应逻辑后测试报错信息精确定位到逻辑失效行。恢复源代码后 `git diff -- frontend/src/components/.../ConceptMapPanel.vue frontend/src/__tests__/.../ConceptMapPanel.test.js` 无输出，与 commit b909ccf 严格一致。

### 验证清单自检（plan 审查清单逐项）

**Task 1 审查清单：**
- ✅ focusedNodeId 使用组件内部 ref（L87，未改为 prop；F001）
- ✅ defineExpose 增量扩展，保留 focusedNodeId 和 clearFocus（L437-444；F002）
- ✅ buildVisibleEdgeList helper 被 buildG6Data 和 relatedEdgeIds 两处共用（F003）
- ✅ 同时处理 `e.source===focus` 和 `e.target===focus`（L183-184；CE-004 护栏）
- ✅ soft 和 hard 两种 prerequisite 类型都被纳入邻居（L180）
- ✅ relatedEdgeIds 使用 `edge-${visibleIndex}` 格式，与 buildG6Data 一致
- ✅ 焦点自身始终在 relatedNodeIds 中（L178 `new Set([focus])`）
- ✅ 空焦点返回空 Set 实例（L177 `if (!focus) return new Set()`）
- ✅ defineExpose 扩展了 relatedNodeIds 和 relatedEdgeIds

**Task 2 审查清单：**
- ✅ node.state.faded（L283）和 edge.state.dimmed/emphasized（L296-303）声明在 G6 Graph config 中
- ✅ watch 监听**组件内部** `focusedNodeId` ref（L422；F001）
- ✅ updateElementStates 读 `focusedNodeId.value`（L354/L357；非 props.focusedNodeId）
- ✅ 边 id 通过 `buildVisibleEdgeList()` helper 获取（L373；F003）
- ✅ createGraph 末尾 `if (focusedNodeId.value) nextTick(updateElementStates)`（L343-347；F004 护栏）
- ✅ 退出焦点调 setElementState({}, true) 清空（L358；CE-005 护栏）
- ✅ graph === null 时早 return（L353）
- ✅ try/catch 包裹 setElementState 调用（L377-379 / L359-361）
- ✅ updateElementStates 暴露在 defineExpose（L443）
- ✅ G6 mock 扩展 `setElementState = vi.fn().mockResolvedValue(undefined)`（test.js L20；F005）
- ✅ 测试通过真实 `graph.handlers['node:click']` 入口驱动焦点，断言 spy 调用参数精确
- ✅ 未使用 updateNodeData 重建节点
- ✅ 焦点自身未被 faded（L365 相关节点 → []）
- ✅ 使用 nextTick 而非 setTimeout（L424）

**Task 3 审查清单：**
- ✅ renderPeersHtml 是纯函数（L381 无副作用）
- ✅ null/undefined/{} 输入返回 ''（L382-384；CE-006）
- ✅ HTML 转义覆盖 `<`, `>`, `&`, `"`, `'`（L394-401 escapeHtml）
- ✅ 模块按字母序排序（L385 `entries.sort([(a], [b]) => a.localeCompare(b))`）
- ✅ 同模块内节点按 name 字母序排序（L387 `sortedList` localeCompare）
- ✅ Tooltip plugin trigger='hover'（L311）
- ✅ enable 谓词检查 `items[0].data.badgeText` 非空字符串（L312-315）
- ✅ getContent 从 crossModulePeers.value 取数（L320）
- ✅ 未直接插入未 escape 的用户数据
- ✅ 未用 Naive UI NPopover 替代
- ✅ enable 非永远 true

### 根因分析（bug fix 时必填，非 bug fix 跳过）

不适用——Phase 2.5 是清理 Phase 2 test_debt（焦点淡化 / 跨模块徽标悬停），非 bug fix。

### 自查（四要素格式）

- **新增文件的边界 case**：
  构造输入：dangling edge `{source:'A', target:'GHOST', type:'prerequisite_hard'}`（GHOST 不在 nodes 集合），focus='B'，验证 helper 过滤后 visibleIndex 仍与 buildG6Data 一致
  运行命令：`cd frontend && npx vitest run src/__tests__/knowledge-tree/ConceptMapPanel.test.js -t "F003 guard"`
  实际输出：
  ```
  Test Files  1 passed (1)
  Tests  1 passed | 32 skipped (33)
  ```
  结论：dangling edge 被 helper 正确过滤，relatedEdgeIds.has('edge-0')=true / has('edge-1')=true (B→C 保持 visibleIndex=1) / has('edge-2')=false，边界 case 通过。反证 CE-007 把 helper 改回原始索引后精确 fail，验证实现真的依赖 helper 共用。

- **状态变量/锁的异常路径**：
  构造输入：clearFocus 后 focusedNodeId.value=null → updateElementStates 走清空分支 → graph.setElementState({}, true) 被调用
  运行命令：`cd frontend && npx vitest run src/__tests__/knowledge-tree/ConceptMapPanel.test.js -t "CE-005"`
  实际输出：
  ```
  Test Files  1 passed (1)
  Tests  1 passed | 32 skipped (33)
  ```
  结论：状态变量清空路径被 spy 捕获，argument === {} + animation === true。反证 CE-005 删除清空分支后，spy.mock.calls.length 无增长，精确 fail。

  **额外异常路径**：graph===null（mount 早期）→ updateElementStates 第一行 `if (!graph) return` 早退；try/catch 包裹 setElementState 调用防 G6 内部抛异常中断 UX（L359/L377）——未单独写测试（G6 mock 的 setElementState 不抛异常），但源代码层级已覆盖。

- **字符串匹配/条件判断的假阴性**：
  构造输入：enable 谓词接收 `[{data:{}}]` / `[]` / `null` 三类退化输入；getContent 接收无 external_hard_refs 节点；renderPeersHtml 接收 `{M2: []}`
  运行命令：`cd frontend && npx vitest run src/__tests__/knowledge-tree/ConceptMapPanel.test.js -t "Phase 2.5 INV-009"`
  实际输出：
  ```
  Test Files  1 passed (1)
  Tests  4 passed | 29 skipped (33)
  ```
  结论：enable 对所有 4 种退化输入返回 false（`!!(item && item.data && item.data.badgeText)` 护栏有效）；getContent 对无 peers 节点返回 ''；renderPeersHtml({M2:[]}) 经 filter 后 entries.length===0 返回 ''。HTML escape 测试同时断言 `not.toContain('<script>')` 和 `toContain('&lt;script&gt;')` 双向，防止 escape 失败的"只不包含不替换"假阴性。

### 语义回归自检

Phase 2.5 **无 semantic_risk**（change_auth.infer_semantic_risk() 未标记——本批次纯前端可视化增量，无 temporal_trace / forbidden_strategy / 状态机转移 / 口径变更）。oracle 表空，跳过。

### Fix Card

不适用（本批次非 review fix，是首次实现）。

### 前端全量回归

```
cd /c/Users/Administrator/edu-cloud/frontend && npx vitest run
Test Files  17 passed (17)
Tests  179 passed (179)
Duration  17.03s
```

期望：17 files / 178 tests（Phase 2 160 + Phase 2.5 18）
实际：17 files / **179 tests**（Phase 2 160 + Phase 2.5 19）
差异说明：Phase 2.5 比 plan 汇总估算多 1 测试——plan Task 3 的测试契约清单列了 8 项 INV-009/INV-010/CE-006 测试但 plan Step 3 估算 "5 tests"（字面 commit message 也写 "+5 tests"），实际按 Task 3 测试契约清单严格落地为 8 项。我选择**按测试契约清单执行**（契约即规格），而非按 commit message 估算数字，因此 +1 改进 🔀 已在逐 Task 自审表 T3 行标注。

### 自治边界声明（视觉任务硬约束）

Phase 2.5 是**视觉任务 + 单科目 + 非离线**（L015/autonomy-boundary 不触发不可自治组合）。但按交接卡 §自治边界规则，Executor 不得自行声明"视觉验收通过"：

- **实现完成，待用户验收**
- **视觉验收路径（design §8 的 3 条）**，请用户手动操作：
  1. 启动前端 dev：`cd /c/Users/Administrator/edu-cloud/frontend && python ~/.claude/scripts/serve.py "C:/Program Files/nodejs/npm.cmd" run dev`
  2. 浏览器打开 http://localhost:5273/knowledge-tree
  3. 切至某模块（例如"分子与细胞"）→ 点击任意节点 → 观察非相关节点/边淡化（opacity 0.3/0.2），相关边粗化（lineWidth 2.5）
  4. 悬停有跨模块徽标的节点（badgeText 非空）→ 观察 Tooltip 弹出 peer 列表（按模块字母序 / 同模块按节点 name 字母序）
  5. ESC 或点击画布空白 → 焦点退出，所有元素恢复默认样式
- **未测试的实际渲染维度**：G6 state 的视觉属性（opacity / lineWidth / stroke）在 happy-dom 下不触发真实绘制；Tooltip plugin 的 DOM 位置与渲染（position / zIndex）依赖浏览器计算，测试只覆盖 plugin wiring 配置。
- 视觉一致性的裁判权在**用户**，不在 Executor。
- **禁止**输出"所有功能已正常 / 全绿汇总"。

### 送 Gate 2 codex-review

下一步：使用 `codex-review` skill mode=code_review 送审 Phase 2.5 Batch 1 两文件改动，预期 PASS。

---

## R1 → R2 修复记录（追加于 2026-04-10 22:42:30）

### Round 1 结果

**Round 1 GPT 审查结论**: FAIL — 详见 `docs/plans/2026-04-10-teacher-workbench-phase2.5-review-report-batch1.md`
**Round 1 commit**: `b909ccf` (Batch 1 实现) + `913e3a0` (R1 审查报告 + GPT 原始输出)

3 个 finding（全部 type=defect_fix，不触发行为变更红旗模式，缺陷修复组批量处置）：
- F001 HIGH (test-gap, INV-009): Tooltip 真实链路未锁住
- F002 MED (test-gap, INV-010): 同模块内 peer 顺序未锁住
- F003 MED (test-gap, INV-006/INV-007): 孤立节点边界未覆盖

### Round 2 修复

**R2 commit**: `f948089 fix(knowledge-tree): Phase 2.5 Batch 1 R2 — F001/F002/F003 test-gap 修复`
**改动文件**: 仅 `frontend/src/__tests__/knowledge-tree/ConceptMapPanel.test.js`（+118 行，3 个新测试）
**实现代码**: 无改动（vue 文件 git diff 空）

| Finding | 修复方式 | 测试函数 | 反证命令 | 反证结果 |
|---------|---------|---------|---------|---------|
| F001 | 从 `graphCtorCalls[last].data.nodes` 取真实 node data 喂给 plugin.enable/getContent，不再手写 items | `INV-009 F001 real link: plugin consumes real buildG6Data badgeText end-to-end` | `npx vitest run -t "F001 real link"` | 临时把 buildG6Data 中 `badgeText` 字段写入改为 `badgeText: ''` → 精确 fail at line 803 `expect(nodeA.data.badgeText.length).toBeGreaterThan(0)`（received 0）→ 恢复后 PASS |
| F002 | 输入乱序 [Zebra, Apple, Mango] + 用严格 indexOf 比较 Apple<Mango<Zebra | `INV-010 F002 intra-module sort: peers within same module sorted by name strictly` | `npx vitest run -t "F002 intra-module sort"` | 临时把 `sortedList = [...list].sort(...)` 改为 `sortedList = [...list]` → 精确 fail at line 842 `expect(mangoIdx).toBeLessThan(zebraIdx)`（141 not less than 97）→ 恢复后 PASS |
| F003 | 构造 ISOLATED 节点（不被任何边触及）+ node:click 真实入口驱动 + stateMap 完整断言（focus=[], 其他=['faded'], 边=['dimmed']）| `F003 isolated node: real node:click on a node with zero edges → relatedNodeIds = {self}, stateMap all others faded` | `npx vitest run -t "F003 isolated node"` | 临时把 relatedNodeIds 的 `new Set([focus])` 改为 `new Set()` → 精确 fail at line 584 `expect(wrapper.vm.relatedNodeIds.size).toBe(1)`（received 0）→ 恢复后 PASS |

**反证验证汇总（R2: 3/3）**: 全部精确 fail，破坏点行号与断言行号对齐。恢复源代码后 `git diff -- frontend/src/components/knowledge-tree/ConceptMapPanel.vue` 无输出。

### R2 全量回归

```
cd /c/Users/Administrator/edu-cloud/frontend && npx vitest run
Test Files  17 passed (17)
Tests  182 passed (182)
Duration  13.00s
```

期望：17 files / 182 tests（Phase 2 160 + R1 19 + R2 3）
实际：17 files / 182 tests ✅

### 行为变更守卫复检

**红旗模式检测**：
- F001 修复 = 改测试用真实数据驱动，无新行为，未改状态机/fallback/选择策略/默认值/资源消耗/时序/评估节奏 → defect_fix ✓
- F002 修复 = 补一条排序断言，未改实现 → defect_fix ✓
- F003 修复 = 补一条边界覆盖测试，未改实现 → defect_fix ✓

三条均为缺陷修复组，无 behavior_change finding，按"分组呈现规则"批量处置，无需用户单独批准。

### Round 2 送审

下一步：再次调用 `codex-review` skill mode=code_review 送审范围 `b909ccf..f948089`（Phase 2.5 Batch 1 实现 + R2 测试增量），期望 PASS。
