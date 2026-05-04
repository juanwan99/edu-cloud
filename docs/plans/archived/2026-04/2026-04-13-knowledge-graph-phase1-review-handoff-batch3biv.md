[edu-cloud] Executor→Reviewer | 2026-04-18 15:05:00

## R4 审查交接单: Batch 3.b.iv（R3-F001 finally guard race mutant 独立修复）

- 计划: `docs/plans/2026-04-13-knowledge-graph-phase1-plan.md`（R6 PASS, subject_hash `a963e85b`）
- 设计: `docs/plans/2026-04-12-knowledge-graph-optimization-design.md`
- 派发 Handoff: `docs/plans/2026-04-13-knowledge-graph-phase1-handoff-batch3biv.md`（Planner 2026-04-18 13:30 派发 @ `73b3fb5`）
- R1 FAIL Handoff: `docs/plans/2026-04-13-knowledge-graph-phase1-review-handoff-batch3biii.md`
- R1 FAIL Report: `docs/plans/2026-04-13-knowledge-graph-phase1-review-report-batch3biii.md`（GPT 5.4 FAIL, R3-F001 HIGH test-gap + P0-F001 MED process）
- Gates: `docs/plans/2026-04-13-knowledge-graph-phase1-gates.json`（batch3b_iii=fail R1 / **batch3b_iv=pending R1 待写**）
- R4 范围: 修 R3-F001 单 finding（HIGH test-gap / defect_fix / red-flag: lifecycle-race finally guard）
- R4 Commit: `43264e1`（test-only，+1 Test C finally race mutant）
- R4 修改文件（白名单 1 个）:
  - `frontend/src/__tests__/knowledge-tree/ExamItemsTab.test.js`（+42 行 / -0 行，1 新 it）
- 用户决策: 2026-04-18 13:28 Option A 批准拆子 batch 3.b.iv（gates_lib R2 升级条件全不满足：T3 非 T4 / 非 remote-deploy / 单文件单模块）
- 严禁改动: `ExamItemsTab.vue`（F001 code 已 R2 resolved-correct，反证 zero-residue 已核对）；3.b.iii 已落盘 Test A/B 不动；W1/W3/W4 / master / 后端 / 其他前端模块 零触

### 环境备注

本 R4 在独立 **W2 worktree** `/home/ops/projects/edu-cloud-w2`，分支 `feat/kg-batch3b` @ `43264e1`。不动 master / 其他 worktree。

### 逐 Task 自审

R4 修复仅 1 个 finding（R3-F001），对应 1 个 Task。

| Task | 计划要求（派发 handoff §Fix Intent Card） | 实际执行 | 状态 | 说明 |
|------|---------|---------|------|------|
| R3-F001 finally race mutant test | 用 2 个 deferred promise；`setProps({ nodeId })` 触发切换入口；**关键时序差异**：resolveA 先发生、resolveB 故意不触发（B pending）；断言 UI 含 '加载中'；resolveB 后断言 UI 切到 B；禁 `mockResolvedValue` / 禁 `setTimeout` / 禁断言 `wrapper.vm.loading`；反证 #1 必须实测粘贴 fail 输出 | 新增 1 个 it（"race condition: A resolve (stale) / B pending, UI 保持 loading (finally guard 锁)"），用 `new Promise((r) => { resolveA = r })` × 2 + `mockReturnValueOnce` × 2；mount nodeId='A' → `setProps({nodeId:'B'})` 触发 fetchSeq=2；resolveA 先（A 的 try+finally guard 均 mySeq=1 !== fetchSeq=2 早退）；`wrapper.text()` 断言含 '加载中' + `not.toContain('stem-A')`；resolveB 后断言含 'stem-B' + `not.toContain('加载中')`；反证 #1 临时注释 L64 `if (mySeq === fetchSeq)` 让 finally 无条件 `loading=false` → 实测 Test C 红并粘贴完整 fail 输出到 §反证矩阵。ExamItemsTab.vue 零改动，反证后 `git diff` 零残留 | ✅ | commit `43264e1`（单 commit，test-only +42/-0） |

> 状态：✅一致 / ❌不一致 / 🔀改进（实现优于计划）

### R3-F001 处置逐项自审

| 项 | 派发 handoff 要求（Fix Intent Card） | 实际执行 | 状态 |
|----|-----|------|------|
| 测试入口 | deferred promise 受控挂起 + `setProps({ nodeId })` 触发 nodeId 切换 | `new Promise((r) => { resolveA = r })` × 2，`getExamItems.mockReturnValueOnce(promA).mockReturnValueOnce(promB)`；mount nodeId='A' → `setProps({nodeId:'B'})` 触发 fetchSeq=2 | ✅ |
| 禁止模式 | ❌ `mockResolvedValue` 同步 / ❌ `setTimeout` 伪造 / ❌ 只断言 `loading.value` 内部 state / ❌ 把 "B 已完成" 当 finally 代理 | 100% 遵守：零 mockResolvedValue / 零 setTimeout / 断言 `wrapper.text()` DOM 文本 '加载中' / 与 3.b.iii Test A/B 时序差异（resolveA 先、resolveB 故意不触发） | ✅ |
| 关键时序 | resolveA 先发生、resolveB 故意不触发（B pending）| 代码实现严格遵守：`resolveA({...}) → await flushPromises()` 后不 resolveB，直接断言 UI 状态；resolveB 在 Test 后半段（第二次 flushPromises 后）| ✅ |
| 断言契约 | 含 '加载中' + `not.toContain('stem-A')` → resolveB 后含 'stem-B' + `not.toContain('加载中')` | Test C 两段断言（4 项）严格对应 | ✅ |

### 反证矩阵（handoff §实施步骤 Step 4 强制实测粘贴）

**反证 #1** — 临时注释 `ExamItemsTab.vue:64` finally 块 `if (mySeq === fetchSeq)`，让 `loading.value = false` 无条件执行
预期：Test C 红（A resolve 后 finally 直接 `loading=false` → UI items=[], total=0 → v-else-if total===0 → 显示"该概念暂无关联高考真题"，断言 `toContain('加载中')` fail）
实测命令：
```bash
cd /home/ops/projects/edu-cloud-w2/frontend
npx vitest run src/__tests__/knowledge-tree/ExamItemsTab.test.js
```
实测 fail 输出（原样粘贴）：
```
 ❯ src/__tests__/knowledge-tree/ExamItemsTab.test.js (8 tests | 1 failed) 166ms
     × race condition: A resolve (stale) / B pending, UI 保持 loading (finally guard 锁) 9ms

⎯⎯⎯⎯⎯⎯⎯ Failed Tests 1 ⎯⎯⎯⎯⎯⎯⎯

 FAIL  src/__tests__/knowledge-tree/ExamItemsTab.test.js > ExamItemsTab > race condition: A resolve (stale) / B pending, UI 保持 loading (finally guard 锁)
AssertionError: expected '该概念暂无关联高考真题' to contain '加载中'

Expected: "加载中"
Received: "该概念暂无关联高考真题"

 ❯ src/__tests__/knowledge-tree/ExamItemsTab.test.js:158:25
    156|
    157|     const loadingText = wrapper.text()
    158|     expect(loadingText).toContain('加载中')  // finally guard 专属锁定
       |                         ^
    159|     expect(loadingText).not.toContain('stem-A')  // try guard 协同（已由 Te…
    160|

 Test Files  1 failed (1)
      Tests  1 failed | 7 passed (8)
```
验证结论：删 finally guard → Test C 失败，Received 文本从 '加载中' 变为 '该概念暂无关联高考真题'。符合逻辑：A 先 settle 时 try guard 拦截 items/total 不被覆盖（维持初始空值），若 finally guard 同时失效则 loading 被关闭，UI 走 `v-else-if total===0` 显示空态。证明 Test C 专属锁定 finally guard ✅

**反证 #2** — 删 try guard（已由 3.b.iii Test A 覆盖，非 finally 专属）
按派发 handoff §Semantic Regression Gate 反证矩阵表 #2 明确 Pre-declare：`finally 专属锁通过反证 #1 证明，无需重复覆盖 try guard`。豁免不执行。

**反证后零残留核对**
```bash
cd /home/ops/projects/edu-cloud-w2
git diff frontend/src/components/knowledge-tree/ExamItemsTab.vue
# 输出：空（零 diff）
```
ExamItemsTab.vue 反证完整恢复原状 ✅

### Fix Card

| Finding | Category | Type | Before | After | Resolved-hypothesis | Status |
|---------|----------|------|--------|-------|---------------------|--------|
| R3-F001 | test-gap | defect_fix | `finally` guard 无"A 先 settle / B pending"场景的 mutant test 锁定；删 L64 `if (mySeq === fetchSeq)` 后 3.b.iii 158 测仍全绿 | 1 新 it（resolveA 先、resolveB 故意不触发）；deferred promise + setProps 入口；断言 '加载中' DOM 文本；反证 #1 实测 guard 删除后必红 | ✅ finally guard lifecycle-race lock via entry-level DOM assertion | resolved-correct |

### 验证清单自检

- ✅ 设计合规：deferred promise pattern 严格遵守派发 handoff 禁忌清单（禁 mockResolvedValue / 禁 setTimeout / 禁断言 wrapper.vm.loading / 禁 "B 已完成" 代理）
- ✅ 入口级：`wrapper.setProps({ nodeId })` + `wrapper.text()` DOM 断言，非直调 wrapper.vm
- ✅ 时序差异精确：resolveA 先发生而 resolveB 故意不触发（与 3.b.iii Test A/B "resolveB 先" 时序严格互补），finally guard 专属路径覆盖
- ✅ 断言精准：Test C 第一段 `toContain('加载中')` + `not.toContain('stem-A')`；第二段 `toContain('stem-B')` + `not.toContain('加载中')`，共 4 项
- ✅ 反证实测粘贴：反证 #1 完整 fail 输出已入本文件（3.b.iii R1 FAIL 直接教训：pre-declare 不能替代实测）
- ✅ ExamItemsTab.vue 零改动：`git diff frontend/src/components/knowledge-tree/ExamItemsTab.vue` 空
- ✅ 白名单 1 文件：`git diff 73b3fb5..43264e1 --name-only` = `frontend/src/__tests__/knowledge-tree/ExamItemsTab.test.js`
- ✅ 子集回归：knowledge-tree 14 files / **159 tests PASS** (R3 基线 158 + R4 +1 finally race mutant，commit 43264e1 @ 2026-04-18 15:00)
- ✅ 其他红线零触：W1/W3/W4 范围 / master / 后端 `src/edu_cloud/*` / 后端 `tests/test_*` / 其他前端模块 / 任何 CLAUDE.md
- ✅ 3.b.iii 已落盘测试不动：Test A/B + F002 2 it + 基础 3 it 全保留，`git diff 121a6c9..43264e1 frontend/src/__tests__/knowledge-tree/ExamItemsTab.test.js --stat` 仅 +42/-0 追加

### 自查（四要素格式）

#### 边界 case（A pending 期间多次 setProps / A 与 B 同时 settle）

构造输入: mount nodeId='A' → `setProps({nodeId:'B'})` → resolveA (A 先 settle)，B 继续 pending

运行命令: `cd /home/ops/projects/edu-cloud-w2/frontend && npx vitest run src/__tests__/knowledge-tree/ExamItemsTab.test.js`

实际输出:
```
 ✓ src/__tests__/knowledge-tree/ExamItemsTab.test.js (8 tests) 145ms
   ✓ race condition: A resolve (stale) / B pending, UI 保持 loading (finally guard 锁)
 Test Files  1 passed (1)
      Tests  8 passed (8)
```

结论: Test C 覆盖"A 先 settle / B pending"场景。若用户实际场景 B 先 settle A 后到 → 3.b.iii Test A/B 已覆盖。A 与 B 几乎同时 settle → Vue microtask 串行消费，fetchSeq 递增语义保持，仍走 guard 比较。Test C 只锁 finally 路径的"loading 不被旧请求关闭"，与 try/catch guard 的"items/total 不被旧请求覆盖"正交。如果用户多次 setProps（C→D→E 连续切换），每次都会 fetchSeq++，最终只有最新 mySeq===fetchSeq 才写状态——Test C 不覆盖多 setProps 的组合，属 scope 外（派发 handoff 白名单仅 1 it）。

#### 状态变量/锁的异常路径（fetchSeq 三处 guard 职责分工）

构造输入: `let fetchSeq = 0` module-scoped；`const mySeq = ++fetchSeq` 入口递增；try/catch/finally 三处 `if (mySeq !== fetchSeq) return` 或 `if (mySeq === fetchSeq) loading.value = false`

运行命令: 3.b.iii 反证 1（删 try guard）+ 反证 2（删 catch guard）+ 本 3.b.iv 反证 #1（删 finally guard）三路径全覆盖

实际输出: 三路径反证实测全通，粘贴 fail 输出均在对应 review-handoff 文件

结论: 三处 guard 职责分工 —— try 锁 items/total 不被旧请求成功写入；catch 锁 items/total 不被旧请求 reject 清空；finally 锁 loading 不被旧请求提前关闭。Test A 锁 try、Test B 锁 catch、Test C 锁 finally，三测 orthogonal 覆盖。派发 handoff 反证矩阵 #2 豁免正当（已由 3.b.iii Test A 覆盖，非 finally 专属）。

#### 字符串匹配/条件判断的假阴性（'加载中' / 'stem-B' / 'stem-A' / '11' / '99' 互不误匹配）

构造输入: Test C 第一段期待 text 含 '加载中'（template `<div v-if="loading" class="loading">加载中…</div>`，唯一来源），不含 'stem-A'；第二段期待含 'stem-B' + 不含 '加载中'

运行命令: 已包含在反证 #1 实测中

实际输出: 反证 #1 Received `'该概念暂无关联高考真题'` —— `toContain('加载中')` 精准 fail（UI 从 loading 态变 empty 态）

结论: '加载中' 作为子串只在 `v-if="loading"` 为 true 时出现，唯一。'stem-A' / 'stem-B' 是 fixture.stem 唯一子串，UI 无其他来源。反证下 UI 切到 'v-else-if total===0' 分支显示 '该概念暂无关联高考真题'，既不含 '加载中' 也不含 'stem-A'/'stem-B'，断言精准锁定 finally guard 删除路径。Test C 第二段反证下的 `toContain('stem-B')` 也会 fail（因为 resolveB 后 B 的 finally guard 仍然生效 loading=false，但 B 的 try guard 正常写入了 items/total=B，所以第二段断言应仍 PASS）——等等，这里需要仔细推理：反证 #1 只删 finally guard，try/catch guard 保留。第二段 resolveB 后 B try guard 写入 items=B / total=11，finally 无条件 loading=false（保持），UI 显示 'stem-B' + 不含 '加载中'，Test C 第二段应 PASS。所以反证 #1 只影响 Test C 第一段（UI 提前 loading=false），第二段不受影响。实测也是 `Tests  1 failed | 7 passed (8)` 仅 1 failed，验证了只有第一段断言 fail。

### 🔀 偏离汇总（审查关注点）

1. **派发 handoff §Semantic Regression Gate 反证矩阵 #2 豁免**：派发 handoff 自明 "finally 专属锁通过反证 #1 证明，无需重复覆盖 try guard"。本 R4 遵守，不做 try guard mutant 二次实测（已由 3.b.iii Test A 反证 1 覆盖，正交职责）。
2. **Test C 反证 #1 下的第二段断言仍 PASS**：反证 #1 只删 finally guard，try/catch guard 保留 → B resolve 后 B 的 try guard 正常写入 items/total，finally 无条件 loading=false（维持 false），Test C 第二段 `toContain('stem-B')` + `not.toContain('加载中')` 仍 PASS。这不影响反证 #1 的锁定力——只要第一段 `toContain('加载中')` fail 就证明 finally guard 专属锁。
3. **Contract Pack P0-F001（3.b.iii R1 FAIL 遗留）**：INV-002/INV-004 verification 映射偏差 → 本 R4 scope 外（属 Phase B T13/T14 范围），按 3.b.iii FAIL report 标 deferred-to-phase-b。Phase B 实施时同步修 Contract Pack 映射。

### 送审准备

1. Baseline: knowledge-tree 子集 14/159 PASS（2026-04-18 15:00）
2. Commit: `43264e1`（test-only 单 commit）
3. Staged 纯净：`git diff 73b3fb5..43264e1 --name-only` = 1 文件（ExamItemsTab.test.js）
4. Worktree w2 独立（主 wt / W1 / W3 / W4 零相互污染）
5. 下一步: `codex-review code_review_batch3b_iv round=1`（subject_ref `commit:43264e1`）
6. gates.json R1 回执待写（PASS/FAIL 由 GPT 决，round=1）
7. R1 PASS 后进 Phase B（Batch 3.c T13 + T14 收尾，按主 finish-handoff §5）
8. R1 FAIL → 按 finding 修，R2 升级条件仍不满足 → 再拆 3.b.v 或 WONTFIX；L015 主动放弃阈值：3 次仍 R1 FAIL → WONTFIX + test_debt TD-004（需 Planner 签字）

---

status: submit-for-review-r1
