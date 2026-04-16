[edu-cloud] GPT Reviewer | 2026-04-10 19:25:05

<!-- anchor: finding-classification -->
## 审查报告: Task 1-3（Batch 1：基础算法与概览面板）

**结论: FAIL**（Round 1）

**送审范围**: commits `7a5ecfb..4bd3733`
**审查交接单**: `docs/plans/2026-04-10-teacher-workbench-review-handoff-batch1.md`
**原始输出**: `docs/plans/.codex-raw-code_review_batch1-20260410T192300.log` (sha256: `fa212b17c4f0d9b1a8434a81a169d279970c3cdc5ed134ef2d38ae5342f30286`)

### 第一段：测试充分性（Test Adequacy）

GPT 独立运行 `npx vitest run`（14 files / 120 tests 全绿）。实现侧无独立的行为错误，FAIL 由测试充分性缺口驱动：

- 存在 2 个 HIGH 级 test-gap：determinism 测试 oracle 不覆盖 INV-001 全量；loadAllModulesQuality partial-failure 测试用弱断言
- 存在 1 个 MED 级 test-gap：`__unknown__` band fallback 分支未覆盖

### 第二段：行为正确性（Behavioral Correctness）

#### 变更理解

本批次引入 3 个前端文件 + 1 个 composable 扩展：

1. **`layoutEngine.js`（新）**: 纯函数式布局算法。输入 `{nodes, edges, bigConceptOrder}`，输出 `{positions, bands, warnings}`。流程为 Kahn toposort 计算 rank → 按 `bigConceptOrder` 分配 band Y 范围 → band 内按 rank 排 X；环节点回退到 `max_rank + 1` 并写入 `warnings: ['cycle_detected']`；`big_concept_id` 不在 `bigConceptOrder` 时归入 `__unknown__` band。意图是让 ConceptMapPanel 使用稳定、确定性的骨架布局，替代 G6 力导向的随机排布
2. **`ModuleStatCard.vue`（新）**: 无状态展示组件，props 包含 moduleId/moduleName/conceptCount/bigConceptCount/reviewedCount/highCount/medCount，渲染模块名 + 两个统计 + 审核进度条 + 可选 HIGH/MED 徽章；click 通过 `@select` 向上发射
3. **`ModuleOverviewPanel.vue`（新）**: 组合组件，基于 `navigation + nodes + edges + modulesQuality` 计算每模块卡片数据和跨模块硬前置边聚合；发射 `select-module` / `refresh-quality`
4. **`useKnowledgeTree.js`（改）**: 追加 `modulesQuality` ref 和 `loadAllModulesQuality()` 函数；对 `M1..M5` 并发调用 `qualityCheck`（`Promise.allSettled`），成功模块提取 `summary.issues_by_severity`，失败模块回退为 `{highCount:0, medCount:0}`

整体意图是教师工作台 Phase 2 的"基础算法层 + 概览入口"——这是 Batch 1，后续 Batch 2 才会把这些组件接入 `KnowledgeTreePage.vue`。本批次不改动任何现有运行时行为（无回归面）。

#### Executor 自审抽检

从自审表随机抽 3 项独立验证：

1. **T1 预审自检「determinism」** — 交接单声称 INV-001 已由该测试覆盖。**抽检结论：不成立**。INV-001 显式声明 `{positions, bands, warnings}` 三字段全量稳定，但 `layoutEngine.test.js` 第 62-65 行只比较 `r1.positions === r2.positions` 和 `r1.bands === r2.bands`，`warnings` 字段被遗漏。→ 升级为 F001
2. **T3 预审自检「Promise.allSettled」** — 交接单声称"如果用 `Promise.all`，任一 reject 会抛到顶层，modulesQuality 仍是初始 `{}`"。**抽检结论：断言机制不足**。实际 `loadAllModulesQuality tolerates partial failures` 只做存在性断言 `toBeDefined()` + `find(zero-count)`，不能证明"失败模块具体位置回退为零"。→ 升级为 F002
3. **T1 自查「空节点边界 case」** — 交接单写"空数组早 return，`positions={}, bands={}` 符合边界契约"。**抽检结论：一致**。`layoutEngine.js:25-27` 确实早 return，测试第 13-14 行断言 `positions/bands` 为空对象。此项成立

Executor 自审对 F001/F002 的关键结论不实（把"断言存在"当作"断言 INV 覆盖"）→ FAIL 触发。

#### 对抗性审查

- **边界输入构造**：
  - 为 layoutEngine 构造 `big_concept_id='BC_MISSING'` 的节点 → plan 第 398 行声明应进入 `__unknown__` band → 实际实现 `layoutEngine.js:82-95` 确实有该分支 → 但测试集完全未覆盖 → F003
  - 为 `loadAllModulesQuality` 构造 M1 成功(HIGH=1)/M2 失败/M3-5 成功 场景 → 现有测试只能检测 modulesQuality 非空 + 有零计数模块，不能检测 M2 是否真的是失败的那一个 → F002
- **异常路径追踪**：
  - `computeLayout` 退化为"常量返回"假实现时，determinism 测试仍能通过（两次调用都返回同一常量）→ F001 的根本问题是测试为自反式断言
- **假阴性检测**：
  - 删除 layoutEngine.js 的 `warnings.push('cycle_detected')` 这一行 → cycle 测试会 FAIL（因为它断言 `result.warnings.toContain('cycle_detected')`）→ 但 determinism 测试不会 FAIL（因为不检查 warnings）→ 证明 determinism 缺少对 warnings 的保护
  - 删除 `loadAllModulesQuality` 中 `rejected → {0,0}` 的回退逻辑 → partial-failure 测试可能 FAIL 也可能 PASS（取决于未定义行为的偶然结果）→ 证明断言不够紧

### 第三段：未测试风险（Non-tested Risks）

Contract Pack 基本完整。test_debt 两项（焦点淡化 / 徽标悬停）理由成立，deadline `2026-05-31` 可接受。INV-004/INV-005 和 CE-002/CE-003 属 Batch 2，本批不阻断。

未被测试覆盖的副作用排查：
- 状态：`modulesQuality` ref 的写入是一次性赋值 `.value = next`（原子），无并发问题
- 时区/空值：无 Date 操作、无 null 解包
- 幂等性：`loadAllModulesQuality` 多次调用幂等（无状态累积）
- 权限/注入：本批次不触碰鉴权和 DOM 注入面

### 发现清单

#### F001

- **Severity**: HIGH
- **Category**: test-gap
- **Type**: defect_fix
- **Status**: verified
- **Before-behavior**: `determinism` 测试仅比较 `positions` 与 `bands`。`computeLayout` 退化为"恒定返回同一结果"的空实现时仍可能通过。handoff 把它映射成 `INV-001` 已覆盖，而 INV-001 声明的是 `{positions, bands, warnings}` 全量稳定
- **After-behavior**: 该用例应在"非平凡布局结果稳定"且 `warnings` 被纳入稳定性验证时才能通过，从而真正支撑 INV-001
- **Inv-conflict**: direct（INV-001）
- **Evidence**:
  - `docs/plans/2026-04-10-teacher-workbench-plan.md:2202` 将 INV-001 定义为 `{positions, bands, warnings}` 全量稳定
  - `frontend/src/__tests__/knowledge-tree/layoutEngine.test.js:54`（`determinism` block）只比较 `positions` 和 `bands`
  - `docs/plans/2026-04-10-teacher-workbench-review-handoff-batch1.md:111` 声称 INV-001 已覆盖
- **Impact**: Contract Pack 的 verification 映射不准确，`layoutEngine.js` 核心风险模块得到虚假的确定性保障
- **Repair hypothesis** (advisory): 把确定性校验绑定到非空、非平凡布局 oracle，并将 `warnings` 纳入判定；禁止继续使用"同输入两次输出相等即可"的自反式断言

#### F002

- **Severity**: HIGH
- **Category**: test-gap
- **Type**: defect_fix
- **Status**: verified
- **Before-behavior**: `loadAllModulesQuality tolerates partial failures` 测试仅断言 `modulesQuality` 已定义 + 存在任意一个零计数模块。即使删掉失败模块的精确映射逻辑（例如把 rejected 路径改为 null/抛错），只要结果里碰巧有任意 `{highCount:0, medCount:0}` 的模块（包括 mockResolvedValue 返回空 issues_by_severity 的成功路径）都可能通过
- **After-behavior**: 测试应固定具体失败模块（如 M2），并验证：5 个 M1-M5 key 全量存在、成功模块保留真实计数、只有失败模块回退为零
- **Inv-conflict**: none
- **Evidence**:
  - `frontend/src/__tests__/knowledge-tree/useKnowledgeTree.test.js:82-92`（loadAllModulesQuality tolerates partial failures 整个测试体）仅用 `toBeDefined()` 和 `find(...zero count...)` 存在性断言
  - `frontend/src/components/knowledge-tree/useKnowledgeTree.js:46`（loadAllModulesQuality 本批新增公共 API）
  - `docs/plans/2026-04-10-teacher-workbench-plan.md:2238` 把该模块列为 risk_module
- **Impact**: 绿色测试不能可靠防止 partial-failure 回退逻辑回归，Batch 1 关键承诺未被钉牢
- **Repair hypothesis** (advisory): 让失败样本具名、位置固定，对成功/失败模块分别做精确断言；禁止使用 `toBeDefined()`、`find(any zero-count)` 充当行为验证

#### F003

- **Severity**: MED
- **Category**: test-gap
- **Type**: defect_fix
- **Status**: verified
- **Before-behavior**: plan 明确把"`big_concept_id` 不在 `bigConceptOrder` 中时进入 `__unknown__` band"列为边界条件，但当前测试集没有覆盖这个分支
- **After-behavior**: 应有专门边界测试，在移除 unknown-band fallback、丢节点或错误分带时稳定失败
- **Inv-conflict**: none
- **Evidence**:
  - `docs/plans/2026-04-10-teacher-workbench-plan.md:398` 声明该边界
  - `frontend/src/components/knowledge-tree/layoutEngine.js:82-95` 实现了 `__unknown__` 分支
  - `frontend/src/__tests__/knowledge-tree/layoutEngine.test.js:9` 起整个 suite 没有任何 `__unknown__` 断言
- **Impact**: `layoutEngine` 兜底路径一旦回归，当前 Gate 2 不会报红，plan 声明的边界条件未兑现
- **Repair hypothesis** (advisory): 为 unknown-band fallback 建立独立 oracle；禁止继续只依赖 happy path BigConcept 数据

<!-- anchor: pass-fail -->
### PASS/FAIL 判定

- F001 (test-gap HIGH) 未修复 → FAIL
- F002 (test-gap HIGH) 未修复 → FAIL
- F003 (test-gap MED) 未修复 → FAIL（test-gap MED 也阻塞 PASS）

**判定**: FAIL

### Finding 分组呈现

<!-- anchor: finding-type -->
**缺陷修复组 (defect_fix, 可批量处置)**:
- F001, F002, F003 — 全部为补齐/加固测试，不触碰运行时实现，非红旗模式

**行为变更组 (behavior_change, 需单独确认)**:
- 无

### 行为变更审批记录

本批次无 behavior_change finding，跳过。

### Round 1 修复计划

Executor 将执行：
1. **F001 修复**: 扩展 `determinism` 测试 oracle — 使用多 BigConcept + 链式 + 分叉的非平凡输入，深度比较 `positions` / `bands` / `warnings` 三字段；另补一个含 cycle 输入的 determinism 测试确保 warnings 字段参与比对
2. **F002 修复**: 重写 `loadAllModulesQuality tolerates partial failures` 测试 — 用 `mockImplementation` 让 M2 具名失败，其余 4 模块返回具名 HIGH/MED 计数；断言 5 个 key 全量存在、M1/M3/M4/M5 保留真实计数、M2 回退为 `{0, 0}`
3. **F003 修复**: 新增 `unknown big_concept_id falls into __unknown__ band` 测试 — 构造一个 `big_concept_id='BC_MISSING'` 的节点，断言 `bands.__unknown__` 存在且节点 Y 落在 `__unknown__` band 范围内
4. **Handoff 更正**: review-handoff-batch1.md 的 INV-001 映射描述改为 "F001 Round 1 修复后覆盖"（当前为已覆盖，不准确）

修复后重跑测试 + 重新送审（Round 2）。
