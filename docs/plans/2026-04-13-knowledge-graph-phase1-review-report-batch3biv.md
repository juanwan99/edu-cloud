[edu-cloud] GPT Reviewer | 2026-04-18 15:08:00

<!-- anchor: finding-classification -->
## 审查报告: Batch 3.b.iv（Round 1）

- 结论: **FAIL**（但 R3-F001 scope 内已 resolved-correct；F001/P0-F001 属 scope 外）
- Reviewer: GPT Codex (gpt-5.4) via codex-cli aiproxy
- Subject: commits `43264e1..2b97201`（+1 finally race mutant test + R4 review-handoff）
- Raw output: `docs/plans/.codex-code-review-raw.log`（SHA256 `9aeadf033ed26a4eb70f987b41aefb92c5947e1fa77543874394d125d7cf0af9`）
- gates.json key: `code_review_batch3b_iv` / round=1 / status=fail
- 派发 handoff: `docs/plans/2026-04-13-knowledge-graph-phase1-handoff-batch3biv.md`（@ `73b3fb5`）
- R4 review handoff: `docs/plans/2026-04-13-knowledge-graph-phase1-review-handoff-batch3biv.md`
- Worktree: `/home/ops/projects/edu-cloud-w2` / 分支 `feat/kg-batch3b`

## 变更理解

R4 修复 R3-F001 HIGH test-gap（finally guard 无异步竞态 mutant test 锁定），单 batch 2 commit:

- `43264e1` test(frontend): ExamItemsTab.test.js +1 it Test C（finally race: A 先 settle / B pending → UI 保持 loading）
- `2b97201` docs(plans): R4 审查交接单 batch3biv（Fix Card + 反证 #1 实测 fail 输出 + 自查四要素）

基线: R3 158 → R4 knowledge-tree 子集 14 files / **159 tests PASS**（+1 finally race mutant）。
ExamItemsTab.vue 零改动（F001 code 已 R2 resolved-correct），反证后 git diff 零残留。

## 对抗性审查

GPT 独立验证:

1. **vitest 子集复跑**: `cd frontend && npx vitest run src/__tests__/knowledge-tree/ExamItemsTab.test.js` → 8/8 PASS；`cd frontend && npx vitest run src/__tests__/knowledge-tree/` → 159/159 PASS ✓
2. **Test C finally guard 验证**: 删 `if (mySeq === fetchSeq)` 无条件 `loading.value = false` → Test C 红（UI 从 '加载中' 变 '该概念暂无关联高考真题'）✓ **R3-F001 已 resolved-correct**
3. **新增测试有效性**: GPT 原话 "本次新增的 finally-race Test C 本身是有效的。它是入口级、受控异步、不是 happy path，且能覆盖 3.b.iii 没锁住的 'A 先 settle / B 仍 pending' 路径；这一点我认可"
4. **Phase 2/3**: "本批没有行为代码变更；在新增测试和 handoff 范围内，我没看到新的行为正确性或未测试副作用问题"
5. **Scope 扩展审查**: GPT 读取整个 `ExamItemsTab.test.js` 并审查**所有 8 个 it**（含基础 3 it + F002 2 it + R3 race 2 it + R4 finally 1 it），在**非本 batch scope 的 `shows empty state when no items` 基础测试**上发现 test-gap → **触发 F001**
6. **Contract Pack 映射核查**: INV-004 + CE-002 仍与仓库现状漂移 → **触发 P0-F001**（process，与 3.b.iii R1 FAIL 同类）

## 第一段: 测试充分性（Test Adequacy）

**R3-F001 finally guard 锁定达标** — GPT 独立 mutant 验证反证 #1 路径锁定成立。

**新增 scope 外 F001 不达标** — GPT 扩大审查范围到整个 `ExamItemsTab.test.js` 文件，在 `shows empty state when no items` 原有基础测试（**非本 R4 新增 / 非 3.b.iii 新增**）上发现 weak assertion：若删除 `watch(..., { immediate: true })` 或 `load()` 主链路，测试仍会通过（组件默认初始态 `total=0, loading=false` 天然落到 `v-else-if total===0` 分支）。

## 第二段: 行为正确性

无新 code-bug。Test C 本身有效，入口时序精确。ExamItemsTab.vue 零改动。

## 第三段: 未测试风险

R3-F001 finally lifecycle guard 已被 Test C 锁定。剩余未被锁定的是 Task 11 最初实现就存在的 "首次 `load()` 实际发生" 契约（`immediate: true` watcher 触发），**属 Task 11 原有测试债务**，非本 R4 / 3.b.iii / 3.b 的衍生 test-gap。

## Findings

### F001

- ID: F001
- Severity: **HIGH**
- Category: test-gap
- Type: defect_fix
- Red-flag: ❌ 非 red-flag（非 lifecycle race，是 happy-path 测试弱断言）
- Scope 判定: **⚠️ scope 外**（非本 batch 3.b.iv 变更文件内容；`shows empty state when no items` 基础测试在 3.b.iii R2-F002 修复之前就已存在，由 Task 11 最初实现引入）
- Before-behavior: `shows empty state when no items` 测试即使删掉 ExamItemsTab 的首次加载核心逻辑（watch immediate / load() 主链路），仍会通过——组件默认初始态 `total=0, loading=false` 天然落到 empty 分支
- After-behavior: 空态测试应当证明"真实发生过一次加载并落到空结果分支"；删掉首次请求 / `watch(..., { immediate: true })` / `load()` 主链路时，测试必须失败
- Evidence:
  - `frontend/src/__tests__/knowledge-tree/ExamItemsTab.test.js:13`（`shows empty state when no items` 基础测试，3 处 `mockResolvedValue` 之一）
  - `frontend/src/components/knowledge-tree/ExamItemsTab.vue:40`（`items = ref([])` 初始值）
  - `frontend/src/components/knowledge-tree/ExamItemsTab.vue:50`（`load()` 主链路）
  - `frontend/src/components/knowledge-tree/ExamItemsTab.vue:71`（`watch(..., { immediate: true })` 触发入口）
- Impact: Task 11 "无关联题展示空态"契约目前没有被有效锁定。未来回归导致组件根本不发请求或丢失 `immediate` 触发，这条测试仍会绿
- Repair hypothesis: 改成受控异步链路，先断言 `mount` 后处于 loading 态（getExamItems 调用前断言），再在 `resolve({ items: [], total: 0 })` 后断言空态；至少让"未发请求 / 未进入 load"时必红

### P0-F001

- ID: P0-F001
- Severity: **MED**
- Category: design-concern
- Type: defect_fix
- Red-flag: ❌ 非 red-flag（process finding / Contract Pack 映射准确性，与 3.b.iii P0-F001 同类）
- Scope 判定: ⚠️ scope 外（与 3.b.iii 同类，属 Phase B T13/T14 范围）
- Before-behavior: Contract Pack 部分 verification/mitigation 映射与仓库现状不一致：
  - `INV-004` 引用 ModuleOverviewPanel `statsOverview=null` 降级断言，但组件与测试都不存在
  - `CE-002` 引用 `test_get_exam_items_endpoint_for_seeded_concept` 测试名，与实际文件不符
- After-behavior: Contract Pack 应只引用真实存在且语义匹配的测试；不存在的 null-contract 覆盖要明确标 deferred
- Evidence:
  - `docs/plans/2026-04-13-knowledge-graph-phase1-plan.md:4036`（INV-004 声明）
  - `docs/plans/2026-04-13-knowledge-graph-phase1-plan.md:4065`（CE-002 声明）
  - `frontend/src/components/knowledge-tree/ModuleOverviewPanel.vue:34`（当前无 statsOverview 降级分支）
  - `frontend/src/__tests__/knowledge-tree/ModuleOverviewPanel.test.js:23`（当前 4 基础用例，无 null 降级断言）
  - `tests/test_knowledge_tree/test_exam_items_service.py:242`（实际测试名与 CE-002 引用不匹配）
- Impact: Phase 0 Contract Pack 校验被文档误导，审查者易把未闭合的 invariant/counter-example 当成已闭合
- Repair hypothesis: 对齐 INV-004 / CE-002 到真实测试名，不存在的覆盖显式转 deferred / test_debt

## 结论

**FAIL**（1 HIGH + 1 MED，均 scope 外）。

### Scope 判定（Executor 主张）

- **R3-F001（本 batch 核心修复目标）**: ✅ resolved-correct（GPT 确认 Test C 有效，finally guard 锁定成立）
- **F001（GPT 新提）**: ⚠️ **scope 外** — `shows empty state when no items` 基础测试非 R4 / 3.b.iii / 3.b 变更引入，属 **Task 11 原有测试债务**，应纳入 Contract Pack test_debt 或 Phase B / 后续 Task 补测
- **P0-F001**: ⚠️ scope 外（与 3.b.iii P0-F001 同类，Phase B T13/T14 范围）

### R2 升级条件判定（gates_lib §Gate 条件）

| 条件 | 检查 | 结果 |
|------|------|------|
| Tier = T4 | 本 topic tier=T3 | ❌ |
| topic 标签含 remote / deploy / publish | `kg-phase1` / `batch3b_iv` 不含 | ❌ |
| 跨模块重构（≥2 文件 + ≥2 模块）| R4 修改 1 文件（`ExamItemsTab.test.js`），1 模块（`knowledge-tree`）| ❌ |

**R2 升级条件均不满足**。

### 建议处置（由 Planner / 用户裁定）

本 R1 FAIL 的核心 scope 内修复（R3-F001 finally guard）已 GPT 验证 resolved-correct。FAIL 源于 GPT 扩大审查 scope 发现的**原有测试债务**，不应递归拆 3.b.v 修 scope 外 finding（risk：3.b.v 再 scope 扩审发现其他基础测试弱点 → 无限拆分）。

| Option | 动作 | 风险 |
|---|---|---|
| **A** 接受 FAIL 状态 + 记 test_debt | R3-F001 finally guard 视为 resolved；F001/P0-F001 入 Contract Pack test_debt TD-005/TD-006；Planner 签 deadline（Phase B T14 或下一季度）；**跳过**阻塞，Phase B 启动（用户需授权 L017 豁免 gate_blocker） | Gate 语义松动，需 Planner 签字 |
| **B** 拆 3.b.v 修 F001 | 新建 `shows empty state` 受控异步改造（loading 先断言 + resolve 后断言），~30 行；但存在 scope 递归风险（3.b.v R1 可能再发现其他 test-gap） | 无限拆分，程序膨胀 |
| **C** WONTFIX R3-F001 + F001 | Planner 级 WONTFIX，test_debt 签字封存，3.b 系列完全停止 | 遗留 lifecycle guard 盲区已 resolved，但 Task 11 测试债务未动 |

**Executor 建议**: Option A（接受 FAIL + test_debt，Phase B 启动）。理由：
1. 本 3.b.iv 核心修复目标（R3-F001 finally guard mutant）已 GPT 独立验证 resolved-correct
2. F001 是 Task 11 原有测试债务，按 codex-review skill §Finding Type "defect_fix"（修复现有缺陷）但 scope 超出 3.b.iv 白名单
3. Phase B T13/T14 是自然补测试的落点（统计/概览 UI 新增 + 收尾审查交接单），正好纳入 F001 基础测试改造
4. 递归拆 3.b.v 违反 L017 "局部最优覆盖全局最优" —— GPT scope 扩审本身是合理的代码质量提醒，但不应作为阻塞 Phase 1 收尾的硬 gate

---

status: submitted-r1-fail-scope-out
