# Plan Review: 知识图谱 Phase 1

> **Round**: R1
> **Reviewer**: GPT Codex gpt-5.4 (via codex-review skill)
> **Timestamp**: 2026-04-13 06:50 UTC+8
> **Plan**: `docs/plans/2026-04-13-knowledge-graph-phase1-plan.md`
> **Raw Log**: `docs/plans/.codex-plan-review-kg-phase1-raw.log`

## 结论: **FAIL** (R1)

3 HIGH code-bug + 3 MED + 1 HIGH design-concern。全部有效，无误报。

## Findings

### F001 [HIGH / code-bug / defect_fix / verified]

**Before**: 按现有仓库基建执行计划，测试应能直接被收集并运行，sync 集成应调用真实入口。
**After**: 计划大量引用仓库中不存在的 fixture / 函数 / 测试文件名，Executor 照单执行会在收集阶段失败。
**Evidence**:
- `db_session` (plan:190, 2006+) → 实际为 `db` (conftest.py:60) 和 `admin_headers` (conftest.py:123)
- `sync_knowledge_tree` (plan:1576/1636) → 实际入口 `sync_knowledge_on_startup` (sync_service.py:188)
- `tests/test_knowledge_tree/test_sync.py` (plan:1622) → 实际文件 `test_sync_startup.py`
**Impact**: 代码库对齐硬失败，Executor 无法执行。
**Status**: **resolved-correct** (R2)

### F002 [HIGH / code-bug / defect_fix / verified]

**Before**: `KnowledgeTreePage` 按当前 props/events 契约驱动 `TreeNavPanel` 与 `ModuleOverviewPanel`。
**After**: Task 12/13 改子组件契约但未同步页面调用方。
**Evidence**: KnowledgeTreePage.vue:13 传 `module-mastery/nodes-with-mastery/selected-module`，新 props 签名 `navigation/nodes/selectedKeys` 不兼容。
**Impact**: 前端运行时 prop/event 失配。
**Status**: **resolved-correct** (R2)

### F003 [HIGH / test-gap / defect_fix / verified]

**Before**: 测试应在删除核心视觉/路由逻辑后明确失败。
**After**: 关键测试是"挂载成功/prop 变了"级别，逻辑镜像或弱断言。
**Evidence**:
- plan:2513 `expect(wrapper.exists()).toBe(true)` 空断言
- plan:2529 `expect(wrapper.props('colorMode')).toBe('review_status')` 只验 prop 传递
- plan:1894 `assert resp.status_code in (200, 404)` 把 404 当 PASS
**Impact**: Graph 着色、节点尺寸、exam-items 路由坏掉也可能被放过。
**Status**: **resolved-correct** (R2)

### F004 [MED / test-gap / defect_fix / verified]

**Before**: 每个行为变更 Task 至少有一个用户可触达入口级验证。
**After**: 多 Task 测试契约停留在内部 helper / service 入口。
**Evidence**: plan:423/719/726/1000/1007/1342/1349/3117 全部是内部函数直接调用，没走 HTTP 或 UI 入口。
**Impact**: 内部函数通过不能证明真实链路正确。
**Status**: **resolved-correct** (R2) — 每个行为 Task 新增 HTTP 端点或 UI 组件挂载级 slice。

### F005 [MED / code-bug / defect_fix / verified]

**Before**: state sidecar 应完整覆盖计划任务。
**After**: Task 0 Step 3 的示例代码用 `range(1, 13)` 只生成 1..12，与正文 Task 0-14 不一致。
**Evidence**: plan:137 vs plan:3556 (Task 14) vs plan:3659 自审称"13 Task"。
**Impact**: 任务追踪失真。
**Status**: **resolved-correct** (R2)

### F006 [HIGH / design-concern / defect_fix / verified]

**Before**: threshold/fallback/lifecycle 公共变更应有 Contract Pack。
**After**: 完全缺失 Contract Pack；正文显式引入 cycle fallback / matching threshold / 无 MCU fallback / startup lifecycle 红旗模式。
**Evidence**: plan、design、gates 无 `invariants/counter_examples/risk_modules/test_debt` 段。
**Impact**: 风险分级无可验证依据，Code Review 难判 defect vs behavior drift。
**Status**: **resolved-correct** (R2) — 新增 §Contract Pack 段。

### F007 [MED / design-concern / behavior_change / verified]

**Before**: `NodeDetailDrawer` 保留 `教材证据(evidence)` 与 `典型真题(questions)` 标签页。
**After**: 计划改为"基本信息/课标/教材/DA/高考真题/学习单元"，移除了原有 evidence + questions。
**Evidence**: NodeDetailDrawer.vue:41/47 现有 → plan:2807 新结构。
**Impact**: 教师现有"教材证据回看"和"典型真题"路径丢失（UX 回退）。
**Status**: **resolved-correct** (R2) — 改为**纯新增**：6 tab → 7 tab，保留 evidence + questions，追加 exam_items + study_unit（避免 behavior_change）。

## R2 修订范围

| 修订 | 涉及 Task | 修订内容 |
|------|-----------|---------|
| 统一 fixture | T1/T3/T5/T6/T7/T8 所有后端测试 | `db_session`→`db`, `auth_headers`→`admin_headers` |
| 统一 sync 函数 | T6 | `sync_knowledge_tree`→`sync_knowledge_on_startup` |
| 统一测试文件 | T6 | `test_sync.py`→`test_sync_startup.py` |
| 页面调用方同步 | T12/T13 | 在文件列表增加 KnowledgeTreePage.vue，示例代码更新调用链 |
| 强化测试断言 | T10/T8 | 替换空断言/弱断言，HTTP 测试明确 200 |
| 入口级 slice | T2/T3/T5/T7/T8/T12 | 每 Task 至少 1 个 HTTP/UI 入口 slice |
| state sidecar | Task 0 | `range(0, 15)` 覆盖 T0-T14 |
| Contract Pack | 新增 §14 | invariants ≥3 / counter_examples ≥2 / risk_modules / test_debt |
| NodeDetailDrawer 保留 | T11 | 7 tab 结构（不移除 evidence + questions） |

R2 审查时所有 finding 应显示 **resolved-correct** 或 **contested+evidence**。

---

## Round 2-6 (2026-04-13 07:00-07:45)

| Round | 结果 | 新增/未解决 |
|-------|------|------------|
| R2 | FAIL | F004 contested + F005 contested + F008 新 MED |
| R3 | FAIL | F009 新 HIGH (chapterTreeData props.nodes.find) |
| R4 | FAIL | F010 新 HIGH (select-node payload 契约降级) |
| R5 | FAIL | F010 test coverage MED（GPT 误读 integration test）|
| R6 | **PASS (substantive)** | F010 verified — 测试实际存在于 plan 3486-3504 |

### F008 [MED / design-concern / defect_fix / verified (R3)]

**Before**: ModuleOverviewPanel 仅显示 avg_freq 和频段条。
**After**: 追加"考频覆盖"字段，来自 get_stats_overview.module_stats[mod].exam_coverage。
**Status**: **resolved-correct** (R3)

### F009 [HIGH / code-bug / defect_fix / verified (R4)]

**Before**: Task 12 chapterTreeData 用 `props.nodes.find(...)`，但 F002 修订删除了 nodes prop。
**After**: 统一使用 `props.nodesWithMastery.find(...)`，与 moduleTree 一致。
**Status**: **resolved-correct** (R4)

### F010 [HIGH / code-bug / defect_fix / verified (R5→R6)]

**Before**: onSelect concept 分支 `emit('select-node', keys[0])` 只传 id 字符串。破坏 TreeNavPanel.vue:147 契约（发完整 node 对象）。
**After**: 改为 `const node = props.nodesWithMastery.find(n => n.id === keys[0]); if (node) emit('select-node', node)`。测试断言 payload 为对象且含 id/name/module 字段（plan:3486-3504）。
**R5 GPT 误判**: GPT 检查了现有 repo 的 integration test 而非 plan 中 component 级测试，报 "测试未锁契约"。
**R6 澄清**: GPT 直读 plan:3486-3504 确认 F010 verified，明确承认 "R5 的 F010 finding 可判为 false_positive"。
**Status**: **resolved-correct** (R6), R5 finding marked **contested → resolved-false-positive**

---

## 最终 Gate 1 结论

**状态**: PASS (substantive, R6 confirmed)
**Round 历史**: R1-R5 FAIL → R6 PASS (10 个 finding 全部 verified, 其中 1 个 false_positive)
**原始输出**: `.codex-plan-review-kg-phase1-{r1..r6}-raw.log` 六份日志
**raw_output_hash**: 以 R6 为最终审查版本
**report_path**: 本文件（`2026-04-13-knowledge-graph-phase1-plan-review.md`）

### Round 摘要

- R1: 7 findings (3 HIGH code-bug + 3 MED + 1 HIGH design) — 全部修复
- R2: 3 残留 (2 contested + 1 MED new) — 全部修复
- R3: F009 HIGH new (chapterTreeData prop error) — 修复
- R4: F010 HIGH new (select-node payload contract break) — 修复
- R5: F010 test coverage MED (GPT 误读) — R6 澄清为 false positive
- R6: 实质 PASS，无 HIGH/MED 未解决

### 执行前检查点

此 plan 现在可用于 Code Review Gate 2 的基准。执行过程中若偏离 Contract Pack 的 invariants 或引入未列 public API 变更，需记为 process finding。
