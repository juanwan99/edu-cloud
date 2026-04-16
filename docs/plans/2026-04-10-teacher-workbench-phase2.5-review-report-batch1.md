[edu-cloud] GPT Reviewer | 2026-04-10 22:48:28

## 审查报告: Phase 2.5 Batch 1 Task 1-3 (Round 2, FINAL PASS)

**结论**: PASS

**轮次**: Round 2（最终 PASS） — Round 1 FAIL 见归档 `docs/plans/2026-04-10-teacher-workbench-phase2.5-review-report-batch1-r1.md`

**审查对象（R2 范围）**:
- commit 范围: `b909ccf..f948089`
  - `b909ccf` — Batch 1 实现（T1-T3）
  - `f948089` — R2 test-gap 修复（仅追加 3 条入口级测试）
- 改动文件累积:
  - `frontend/src/components/knowledge-tree/ConceptMapPanel.vue`（+176 / −10，仅 R1 commit，R2 未改实现）
  - `frontend/src/__tests__/knowledge-tree/ConceptMapPanel.test.js`（+534 / −0）
  - `CLAUDE.md`（+1 / −1，doc_sync_guard 触发同步）
- handoff: `docs/plans/2026-04-10-teacher-workbench-phase2.5-review-handoff-batch1.md`（含 R1→R2 修复记录追加段）
- plan: `docs/plans/2026-04-10-teacher-workbench-phase2.5-plan.md`

**GPT 原始输出**:
- R1: `docs/plans/.codex-raw-code_review-20260410-222742.log` (SHA256: `5bc909d9abf962006f513af0d4d9785088d2dbcae6ea2a40c5ce707d1e754706`)
- R2: `docs/plans/.codex-raw-code_review_r2-20260410-224230.log` (SHA256: `3d01c71da56b12de69b95d481c379bd1f713d660094c9bc757d5b6d7acbf5f4e`)

---

### 第一段：测试充分性（Test Adequacy）

R1 的 3 个 test-gap finding 均已通过入口级测试修复（详见 Phase 0 复检）。R2 增量的 3 条测试本身不是逻辑镜像，反证方向有效，未引入新的弱断言。Phase 2.5 共 22 个测试（R1 19 + R2 3），覆盖 5 个 INV (INV-006/007/008/009/010) 和 5 个 CE (CE-004/005/006/007/008)。GPT 评估："本轮未发现新的 code-bug 或 test-gap。"

### 第二段：行为正确性（Behavioral Correctness）

#### 变更理解（GPT 复述）

本批次是 Phase 2 延后项清理，纯前端单点增量：在 `ConceptMapPanel.vue` 内新增 `buildVisibleEdgeList()` 共享 helper（与 `buildG6Data` 共用过滤索引，防止 dangling edge 导致 edge-id 偏移）、`relatedNodeIds`/`relatedEdgeIds` 两个 computed（1 跳邻居集合）、`updateElementStates()` 函数（通过 `graph.setElementState(stateMap, true)` 批量驱动 G6 node/edge state），并在 G6 Graph config 中追加 `node.state.faded` / `edge.state.dimmed/emphasized` 样式规范、`plugins: [{type:'tooltip', trigger:'hover', enable, getContent}]` 配置，`createGraph()` 末尾追加 `if (focusedNodeId.value) nextTick(updateElementStates)` 焦点重放；`watch(focusedNodeId, ...)` 监听组件内部 ref 变化；新增 `renderPeersHtml(peers)` 纯函数生成 Tooltip HTML 内容（null/{}/空列表返回 ''、模块字母序 + 同模块 name 字母序 + HTML escape 防注入）；`defineExpose` 增量扩展；G6 mock 追加 `setElementState = vi.fn().mockResolvedValue(undefined)` spy。

**R2 增量**：`ConceptMapPanel.vue` 无改动；`ConceptMapPanel.test.js` 追加 3 条测试：`INV-009 F001 real link`（真实 `graphCtorCalls[last].data.nodes` 喂 plugin）、`INV-010 F002 intra-module sort`（严格 indexOf 断言同模块内排序）、`F003 isolated node`（真实 `node:click` 驱动孤立节点 focus + 完整 stateMap 断言）。

意图是实现 Phase 2 test_debt 中的两项：焦点模式视觉淡化 + 跨模块徽标悬停展开 peer 列表；R2 进一步补强测试入口级覆盖与反证强度。无后端改动、无新依赖、无架构变更；桥接/对比边 deferred 到 Phase 3。

#### Executor 自审抽检

GPT 通过读取 handoff 的"逐 Task 自审表"和"预审自检"做抽检：
- T1 "buildVisibleEdgeList helper 被 buildG6Data 和 relatedEdgeIds 两处共用" → `ConceptMapPanel.vue:205`（buildG6Data 调 helper）+ `:191`（relatedEdgeIds 调 helper）确认属实
- T2 "F004 graph rebuild 测试通过真实 node:click 入口驱动 + 新 graph 实例 setElementState 断言重放" → `ConceptMapPanel.test.js:551` 确认属实
- R2 "F001/F002/F003 三条入口级测试与反证记录" → `ConceptMapPanel.test.js:774/823/564` 三条新测试确认属实；反证行号（803/842/584）与 R2 handoff 记录一致

#### 对抗性审查（边界/异常/假阴性）

GPT 确认本轮 R2 未引入新缺陷：
- **边界输入构造**：孤立节点 `edges=[]` / 稀疏图场景已由 `F003 isolated node` 测试覆盖
- **异常路径追踪**：从 `external_hard_refs` 到 `badgeText` 到 tooltip 的真实链路已由 `F001 real link` 测试锁住
- **假阴性检测**：同模块内 peer 顺序已由 `F002 intra-module sort` 用严格 indexOf 而非 `toContain` 锁住

GPT 确认静态代码本身没有更高优先级的直接实现错误：
- 调用面 `KnowledgeTreePage.vue:47` 未变化，向后兼容
- `layoutEngine.js:14` 会为输入节点分配坐标，helper 过滤语义无额外漂移风险
- Tooltip 回调形状（async getContent + Promise<HTMLElement|string>）与 G6 官方文档一致（https://g6.antv.antgroup.com/en/manual/plugin/tooltip）

### 第三段：未测试风险（Non-tested Risks）

残余风险与 R1 相同，不阻断 R2 PASS：
- 真实浏览器中的 G6 渲染时序
- Tooltip DOM 定位 / z-index
- `faded/dimmed/emphasized` 的最终视觉效果

handoff 已明确这部分交给手工验收（design §8 三条路径）。

---

### 发现清单（R1 回顾 + R2 复检）

#### F001（R1→R2 resolved-correct）

- **Severity**: HIGH
- **Category**: test-gap
- **Type**: defect_fix
- **Status**: verified
- **Terminal**: resolved-correct
- **Before-behavior**: 即使 `buildG6Data()` 不再把真实 `badgeText` 写入 G6 node data，原测试仍可能全绿。
- **After-behavior**: 现在测试直接从真实 `graphCtorCalls[last].data.nodes` 取 node data，再喂给 `plugin.enable/getContent`；如果清空 `badgeText` 写入，测试会失败。
- **Evidence**:
  - `ConceptMapPanel.test.js:774`（`INV-009 F001 real link` 测试函数）
  - `ConceptMapPanel.vue:205`（buildG6Data badgeText 写入）
  - `ConceptMapPanel.vue:304`（plugins 配置）
- **Impact**: INV-009 的真实链路 `external_hard_refs → badgeText → tooltip.enable/getContent` 已被入口级测试锁住。

#### F002（R1→R2 resolved-correct）

- **Severity**: MED
- **Category**: test-gap
- **Type**: defect_fix
- **Status**: verified
- **Terminal**: resolved-correct
- **Before-behavior**: 删除同模块内 `sortedList.sort(...)` 后，原测试仍可能通过。
- **After-behavior**: 现在用乱序输入 `[Zebra, Apple, Mango]`，并用严格 `indexOf` 断言 `Apple < Mango < Zebra`；去掉排序会失败。
- **Evidence**:
  - `ConceptMapPanel.test.js:823`（`INV-010 F002 intra-module sort` 测试函数）
  - `ConceptMapPanel.vue:372`（sortedList.sort 同模块排序）
  - `ConceptMapPanel.vue:378`（renderPeersHtml 输出）
- **Impact**: INV-010 的"同模块内按 name 字母序排序"现在被真实保护，不再是弱断言。

#### F003（R1→R2 resolved-correct）

- **Severity**: MED
- **Category**: test-gap
- **Type**: defect_fix
- **Status**: verified
- **Terminal**: resolved-correct
- **Before-behavior**: 孤立节点场景未通过真实 `node:click` 入口覆盖，`relatedNodeIds` 和完整 `stateMap` 退化可能漏检。
- **After-behavior**: 现在用真实 `graph.handlers['node:click']` 驱动 `ISOLATED` 节点，断言 `relatedNodeIds={self}`、`relatedEdgeIds` 为空、且完整 `stateMap` 为 "self=[] / others=['faded'] / edges=['dimmed']"；若 `new Set([focus])` 改成空集合会失败。
- **Evidence**:
  - `ConceptMapPanel.test.js:564`（`F003 isolated node` 测试函数）
  - `ConceptMapPanel.vue:170`（relatedNodeIds computed）
  - `ConceptMapPanel.vue:343`（updateElementStates）
- **Impact**: INV-006/INV-007 的孤立节点边界已被真实入口测试覆盖，R1 缺口关闭。

---

### PASS/FAIL 判定

按 `~/.claude/rules-t3/review-templates.md` PASS/FAIL 规则：
- R1 的 F001/F002/F003 三个 test-gap finding 全部终态 `resolved-correct`
- R2 Phase 0 复检无新 code-bug / test-gap
- Phase 1-3 未发现新缺陷
- 前端全量 `17 files / 182 tests PASS`，无回归

**结论**: PASS

---

### 行为变更审批记录

全部 finding `type=defect_fix`，无 `behavior_change` finding，无需用户单独批准。红旗模式检测：
- R2 三条修复均为补测试（真实链路、严格排序断言、孤立节点边界），不触发状态机/fallback/选择策略/阈值/生命周期/评估节奏等红旗模式 → defect_fix ✓

---

### R2 全量回归

```
cd /c/Users/Administrator/edu-cloud/frontend && npx vitest run
Test Files  17 passed (17)
Tests  182 passed (182)
```

### 限制声明

两轮审查中 GPT codex exec shell 工具均启动失败，无法直接运行 `git log` / `git diff`。改为通过 `.git/logs/refs/heads/master` 确认审查对象、通过 filesystem MCP 读取 diff 原文与改动文件全文。结论的有效性不受此限制影响。
