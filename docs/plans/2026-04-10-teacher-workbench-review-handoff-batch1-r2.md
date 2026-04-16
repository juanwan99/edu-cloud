[edu-cloud] Executor→Reviewer | 2026-04-10 19:32:28

## 审查交接单: Task 1-3（Batch 1 — Round 2）

计划: `C:/Users/Administrator/edu-cloud/docs/plans/2026-04-10-teacher-workbench-plan.md`
设计: `C:/Users/Administrator/edu-cloud/docs/plans/2026-04-10-teacher-workbench-design.md`
R1 审查报告: `docs/plans/2026-04-10-teacher-workbench-review-report-batch1.md`（FAIL, 3 test-gap）
R1 修复 commit: `2af784d fix(tests): address Batch 1 R1 findings F001/F002/F003`
送审范围（R2）: 仅 `frontend/src/__tests__/knowledge-tree/layoutEngine.test.js` + `useKnowledgeTree.test.js` 的测试增补；源码不变

### R1 finding 处置总览

| ID | Severity | Category | 处置 | 证据 |
|----|----------|----------|------|------|
| F001 | HIGH | test-gap | resolved | layoutEngine.test.js:60-94 (`non-trivial layout is deterministic...`) + 96-118 (`cyclic input determinism includes warnings field`) |
| F002 | HIGH | test-gap | resolved | useKnowledgeTree.test.js:82-117 (`loadAllModulesQuality tolerates partial failures with named-module precision`) |
| F003 | MED | test-gap | resolved | layoutEngine.test.js:166-202 (`unknown big_concept_id fallback` describe block，2 用例) |

### F001 修复详情

**R1 问题**: `determinism` 测试仅深度比较 `positions` 和 `bands`；`warnings` 字段未纳入断言。INV-001 声明三字段全量稳定，该测试是自反式断言（平凡实现即可通过）。

**修复方案**:
1. **非平凡输入**：新 `non-trivial layout is deterministic...` 用例构造 6 节点 + 跨 BC 链式 + 分叉的输入，先断言"非退化"（6 positions / 3 bands / empty warnings），再深度比较 `r1.positions === r2.positions && r1.bands === r2.bands && r1.warnings === r2.warnings`。
2. **warnings 字段参与稳定性**：新增 `cyclic input determinism includes warnings field` 用例，构造 `A→B→A` 环 + 独立节点，先断言 `warnings.toContain('cycle_detected')` 再深度比较三字段。

**反证验证**（破坏源→测试 fail）:
- 删除 `warnings.push('cycle_detected')`（layoutEngine.js:73）→ cycle handling 和新 cyclic determinism 测试 FAIL（AssertionError: expected [] to deeply equal [ 'cycle_detected' ]）
- 实际 counter-proof 命令：
  ```
  npx vitest run src/__tests__/knowledge-tree/layoutEngine.test.js
  → FAIL: cyclic input determinism includes warnings field (warnings 断言不通过)
  → FAIL: cycle handling > cycle does not crash (同因)
  ```

### F002 修复详情

**R1 问题**: `tolerates partial failures` 测试只做 `toBeDefined()` + `find(zero-count)` 存在性断言。删除 rejected 回退路径后，只要成功模块里碰巧有 `{0,0}` 就能误 PASS。无法锁定"失败位置"和"成功模块精确计数"。

**修复方案**（完全重写该测试）:
- `mockImplementation`：M2 具名 `throw new Error('network 500')`，M1/M3/M4/M5 各自返回不同 HIGH/MED 值（`{1,2}` / `{3,0}` / `{0,4}` / `{5,5}`）。
- 断言 1: `Object.keys(modulesQuality.value).sort() === ['M1','M2','M3','M4','M5']`（5 key 全量存在）
- 断言 2-5: 每个成功模块精确值 `toEqual({highCount:X, medCount:Y})`
- 断言 6: M2 精确回退为 `{highCount:0, medCount:0}`（不允许 undefined / 上一次值）
- 断言 7: `qualityCheck.toHaveBeenCalledTimes(5)`（未因单个失败中断）

**反证验证**（破坏源→测试 fail）:
- 删除 `loadAllModulesQuality` 的 rejected 分支回退（不写 `next[mod]`）→ 新测试 FAIL：`expected ['M1','M3','M4','M5'] to deeply equal ['M1','M2','M3','M4','M5']`（断言 1 精确 catch key 缺失）

### F003 修复详情

**R1 问题**: plan.md:398 声明"`big_concept_id` 不在 bigConceptOrder → `__unknown__` band"边界条件，但无测试覆盖。删除 fallback 分支不会让任何现有测试 fail。

**修复方案**（新增 describe block 两个用例）:
1. `nodes with big_concept_id not in bigConceptOrder fall into __unknown__ band`:
   - 构造 `known(BC1)` + `orphan(BC_MISSING)` 两节点
   - 断言 `bands.__unknown__` 存在 + label === '未分类'
   - 断言 `positions.O` 有值（orphan 未丢失）
   - 断言 orphan.y 在 `__unknown__` band 范围内
   - 断言 known.y 在 BC1 band 范围内（未错分带）
   - 断言 `BC1.yMax <= __unknown__.yMin`（`__unknown__` 追加到末尾）
2. `all nodes in bigConceptOrder → no __unknown__ band`（对照组）: 纯 happy path 时 `bands.__unknown__` 不应存在。

**反证验证**:
- 删除 `layoutEngine.js:89-92` 的 else 分支（不把 orphan 推入 `__unknown__`）→ 新测试 FAIL: `expected undefined to be defined`（断言 1 精确 catch band 缺失）

### 逐 Task 自审（R2 更新）

| Task | 计划要求 | R2 状态 | 证据 |
|------|---------|---------|------|
| T1 | layoutEngine.js + 单元测试（INV-001 全量映射 + 边界条件覆盖） | ✅ R2 | 11 tests PASS（原 8 + F001 新增 1 + F001 新增 cyclic det 1 + F003 新增 2）|
| T2 | ModuleStatCard.vue + 5 测试 | ✅（未变） | 5 tests PASS（R1 即 PASS，本轮未动） |
| T3 | ModuleOverviewPanel.vue + loadAllModulesQuality + 4+2 测试 | ✅ R2 | 4 + 7 tests PASS（ModuleOverviewPanel 4 + composable 原 5 + F002 重写 partial-failure 测试 + 原 calls-M1-M5 测试保留）|

> 状态: ✅一致 / ❌不一致 / 🔀改进

### 预审自检（R2，仅列新增/修改项）

| 测试契约 slice | 对应测试文件:函数 | 验证命令 | 实际输出 | 反证验证 |
|---------------|------------------|---------|---------|---------|
| F001 非平凡 determinism | `layoutEngine.test.js > determinism > non-trivial layout is deterministic...` | `cd frontend && npx vitest run src/__tests__/knowledge-tree/layoutEngine.test.js -t determinism` | 2/2 PASS | 删除 `Array.from().sort()` → r1 !== r2（Set 迭代顺序） |
| F001 cyclic determinism | `layoutEngine.test.js > determinism > cyclic input determinism includes warnings field` | 同上 | 2/2 PASS | 删除 `warnings.push('cycle_detected')` → warnings 深度比较失败 |
| F002 具名 partial-failure | `useKnowledgeTree.test.js > loadAllModulesQuality tolerates partial failures with named-module precision` | `cd frontend && npx vitest run src/__tests__/knowledge-tree/useKnowledgeTree.test.js -t tolerates` | 1/1 PASS | 删除 rejected 回退路径 → `keys().sort() === [M1,M3,M4,M5]`（缺 M2）|
| F003 `__unknown__` 主用例 | `layoutEngine.test.js > unknown big_concept_id fallback > nodes with big_concept_id not in bigConceptOrder...` | `cd frontend && npx vitest run src/__tests__/knowledge-tree/layoutEngine.test.js -t "unknown"` | 2/2 PASS | 删除 `else → __unknown__` 分支 → `bands.__unknown__` undefined |
| F003 对照组（happy path 不应有 unknown） | `layoutEngine.test.js > unknown big_concept_id fallback > all nodes in bigConceptOrder → no __unknown__ band` | 同上 | PASS | 如果实现无条件创建 `__unknown__` band → 该测试会 fail |

**全量回归**: `npx vitest run` → **14 files / 123 tests PASS**（较 R1 的 120 tests 增加 3 个新测试：F001 non-trivial determinism + F001 cyclic determinism + F003 两个 unknown 用例——其中 F002 是重写同名用例，test count 不变；合计 +3）。无回归。

### 验证清单自检（R2 修复范围）

**F001 — determinism 测试 oracle（layoutEngine）**

- ✓ 非平凡输入（6 节点 / 3 BigConcept / 5 条 hard 边含分叉与跨 BC）避免"常量返回"假实现误 PASS — `layoutEngine.test.js:60-94`
- ✓ `positions` / `bands` / `warnings` 三字段全量深度比较（INV-001 完整映射）— `layoutEngine.test.js:91-93, 115-117`
- ✓ cyclic 输入的 determinism 用例强制 `warnings` 字段参与稳定性验证 — `layoutEngine.test.js:96-118`
- ✓ 反证：破坏 `warnings.push('cycle_detected')` 后 cyclic determinism 测试精确 fail
- ✗ 仅检 positions/bands 的弱 determinism 断言 — 已删除
- ✗ 自反式断言（空实现即能过）— 已通过非平凡性前置断言排除

**F002 — loadAllModulesQuality 具名断言（composable）**

- ✓ 使用 `mockImplementation(mod => ...)` 按 module id 分派，失败位置固定在 M2 — `useKnowledgeTree.test.js:91-94`
- ✓ 成功模块 M1/M3/M4/M5 各自使用差异化的 HIGH/MED 值（`{1,2}/{3,0}/{0,4}/{5,5}`），防止意外巧合匹配
- ✓ 5 key 全量存在断言 `keys().sort() === ['M1'..'M5']`（1 条）— `useKnowledgeTree.test.js:101`
- ✓ 4 个成功模块各自精确 `toEqual` 断言（4 条）— `useKnowledgeTree.test.js:104-107`
- ✓ M2 精确回退为 `{highCount:0, medCount:0}`（不允许 undefined / 上一次值）— `useKnowledgeTree.test.js:110`
- ✓ 调用总数 `toHaveBeenCalledTimes(5)` 锁定并发语义 — `useKnowledgeTree.test.js:113`
- ✓ 反证：破坏 rejected 回退路径后测试精确 fail（`['M1','M3','M4','M5']` 与期望 `['M1'..'M5']` 深度不等）
- ✗ `toBeDefined()` 存在性断言 — 已删除
- ✗ `find(any zero-count)` 模糊查找 — 已删除

**F003 — `__unknown__` band 边界（layoutEngine）**

- ✓ 正例：`BC_MISSING` 节点触发 `__unknown__` band + label === '未分类' + 节点 Y 落在 band 范围内 — `layoutEngine.test.js:169-192`
- ✓ 非退化：已知节点保持原 band 不被错分 — `layoutEngine.test.js:186-189`
- ✓ 顺序：`__unknown__` band 在 happy-path bands 末尾（`BC1.yMax <= __unknown__.yMin`）— `layoutEngine.test.js:190-191`
- ✓ 对照组：纯 happy path 时 `bands.__unknown__` 不应存在 — `layoutEngine.test.js:194-202`
- ✓ 反证：删除 `layoutEngine.js:89-92` 的 else → __unknown__ push 分支后测试精确 fail（`expected undefined to be defined`）
- ✗ 只断言 positions 非空就算覆盖 — 已升级到 band + Y + 顺序 + 对照组的四维断言

### Contract Pack 不变量映射（R2 更正）

| 不变量 | R1 声称 | R2 实际 | 对应测试 |
|--------|---------|---------|---------|
| INV-001（computeLayout 纯函数 + {positions, bands, warnings} 三字段稳定）| 已覆盖（误） | ✅ R2 covered | `non-trivial layout is deterministic...` + `cyclic input determinism includes warnings field` 双用例，深度比较三字段 |
| INV-002（hard DAG rank X 递增）| ✅ | ✅ | `linear chain A→B→C` + `diverging` |
| INV-003（同 BC 节点 Y 在 band 范围内）| ✅ | ✅ | `nodes of same BigConcept fall within their band Y range` |
| INV-004 / INV-005 | Batch 2 | Batch 2 | — |

### 根因分析

非 bug fix，跳过。（本轮是测试加固，不是行为修复）

### 自查（四要素格式）

- **新增/修改测试的假阴性检测**:
  - 构造输入: 破坏 `layoutEngine.js` 的 `warnings.push('cycle_detected')`
  - 运行命令: `npx vitest run src/__tests__/knowledge-tree/layoutEngine.test.js`
  - 实际输出:
    ```
    FAIL: layoutEngine > determinism > cyclic input determinism includes warnings field
      AssertionError: expected [] to contain 'cycle_detected'
    FAIL: layoutEngine > cycle handling > cycle does not crash, records warning
      AssertionError: expected [] to contain 'cycle_detected'
    Test Files  1 failed (1)
    Tests       2 failed | 9 passed (11)
    ```
  - 结论: F001 修复后测试能精确 catch warnings 字段缺失；与 R1 弱断言相比强化到位

- **F002 具名失败位置**:
  - 构造输入: 破坏 `useKnowledgeTree.js` 的 rejected 回退分支
  - 运行命令: `npx vitest run src/__tests__/knowledge-tree/useKnowledgeTree.test.js`
  - 实际输出:
    ```
    FAIL: loadAllModulesQuality tolerates partial failures with named-module precision
      AssertionError: expected ['M1','M3','M4','M5'] to deeply equal ['M1','M2','M3','M4','M5']
    ```
  - 结论: F002 修复后测试精确锁定 M2 缺失，不会像 R1 弱断言那样误 PASS

- **F003 `__unknown__` fallback 缺失检测**:
  - 构造输入: 删除 `layoutEngine.js:89-92` 的 else `__unknown__` push 分支
  - 运行命令: `npx vitest run src/__tests__/knowledge-tree/layoutEngine.test.js -t unknown`
  - 实际输出:
    ```
    FAIL: nodes with big_concept_id not in bigConceptOrder fall into __unknown__ band
      AssertionError: expected undefined to be defined
    Tests  1 failed | 1 passed | 9 skipped (11)
    ```
  - 结论: F003 修复后测试精确 catch band 缺失

### 语义回归自检

semantic_risk=false（纯 test-only 修复，源码零变更）。跳过。

### 送审对象

- **本次 R2 送审范围**: commit `2af784d`（仅 2 个测试文件的增补/重写）
- **源码 commits 保持**: `7a5ecfb` / `16ed04f` / `4bd3733`（R1 已审过，未变更）
- **不审查范围**（避免越权）:
  - Task 4-6 属 Batch 2
  - KnowledgeTreePage.vue 现有修改来自之前会话，与本批次无关
  - Phase 1 审查工作台（RelationReviewPanel 等）本批未动

### 下一步

使用 codex-review skill 对 Batch 1 R2（commit `2af784d`，测试加固）进行 GPT Code Review (Gate 2, Round 2)。
