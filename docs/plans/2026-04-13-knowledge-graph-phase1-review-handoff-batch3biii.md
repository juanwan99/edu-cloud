[edu-cloud] Executor→Reviewer | 2026-04-18 13:10:00

## R3 审查交接单: Batch 3.b.iii（R2-F001 race mutant test 独立修复）

- 计划: `docs/plans/2026-04-13-knowledge-graph-phase1-plan.md`（R6 PASS, subject_hash `a963e85b`）
- 设计: `docs/plans/2026-04-12-knowledge-graph-optimization-design.md`
- 派发 Handoff: `docs/plans/2026-04-13-knowledge-graph-phase1-handoff-batch3biii.md`（Planner 2026-04-18 派发 @ `80b57fb`）
- R2 FAIL Handoff: `docs/plans/2026-04-13-knowledge-graph-phase1-review-handoff-batch3b-r2.md`
- R2 FAIL Report: `docs/plans/2026-04-13-knowledge-graph-phase1-review-report-batch3b-r2.md`（GPT 5.4 FAIL, 1 HIGH test-gap R2-F001）
- Gates: `docs/plans/2026-04-13-knowledge-graph-phase1-gates.json`（batch3b=fail R2 / **batch3b_iii=pending R1 待写**）
- R3 范围: 修 R2-F001 单 finding（HIGH test-gap / defect_fix / red-flag: lifecycle-race）
- R3 Commit: `121a6c9` (test-only，+2 race mutant it)
- R3 修改文件（白名单 1 个）:
  - `frontend/src/__tests__/knowledge-tree/ExamItemsTab.test.js`（+60 行 / -0 行，2 新 it）
- 严禁改动: `ExamItemsTab.vue`（F001 code 已 R2 resolved-correct，反证 zero-residue 已核对）；W1/W3/W4 / master / 后端 / 其他前端模块 零触

### 环境备注

本 R3 在独立 **W2 worktree** `/home/ops/projects/edu-cloud-w2`，分支 `feat/kg-batch3b` @ `121a6c9`。不动 master / 其他 worktree。

### 逐 Task 自审

R3 修复仅 1 个 finding（R2-F001），对应 1 个 Task。

| Task | 计划要求（派发 handoff §Fix Intent Card） | 实际执行 | 状态 | 说明 |
|------|---------|---------|------|------|
| R2-F001 race mutant test | 用 2 个 deferred promise 受控挂起 `getExamItems`；`setProps({ nodeId })` 触发切换入口；覆盖 resolve race + reject race；禁 `mockResolvedValue` 同步 / 禁 `setTimeout` 伪造 / 禁只断言调用参数；反证 1+2 必须实测粘贴 fail 输出 | 新增 2 个 it（"race condition: B resolve → A resolve" + "race condition: B resolve → A reject"）均用 `new Promise((r) => { resolveA = r })` 受控挂起 + `mockReturnValueOnce` × 2；断言 `wrapper.text()` DOM 内容含 'stem-B'/'11'，Test A 另加 `not.toContain('stem-A'/'99')`；反证 1+2 临时注释 try/catch guard → 实测 Test A/Test B 红并粘贴完整 fail 输出到本卡 §反证矩阵。ExamItemsTab.vue 零改动，反证后 `git diff` 零残留 | ✅ | commit `121a6c9`（单 commit，test-only +60/-0） |

> 状态：✅一致 / ❌不一致 / 🔀改进（实现优于计划）

### R2-F001 处置逐项自审

| 项 | 派发 handoff 要求（Fix Intent Card） | 实际执行 | 状态 |
|----|-----|------|------|
| 测试入口 | deferred promise 受控挂起 + `setProps({ nodeId })` 触发 nodeId 切换 | `new Promise((r) => { resolveA = r })` × 2，`getExamItems.mockReturnValueOnce(promA).mockReturnValueOnce(promB)`；mount nodeId='A' → `setProps({nodeId:'B'})` 触发 fetchSeq=2 | ✅ |
| 禁止模式 | ❌ `mockResolvedValue` 同步 / ❌ `setTimeout`/`sleep` 伪造竞态 / ❌ 只断言调用参数 | 100% 遵守：零 mockResolvedValue / 零 setTimeout / 断言 `wrapper.text()` DOM 内容 | ✅ |
| 两路径覆盖 | resolve race (try guard) + reject race (catch guard) | Test A: resolveB 先 → resolveA 晚到；Test B: resolveB 先 → rejectA 晚到 | ✅ |
| 断言契约 | text 含 'stem-B' + '11'，Test A 另加 not.toContain 'stem-A'/'99' | Test A 4 断言 (含/不含 × 2)，Test B 2 断言（不加 not — reject catch 块本身清空，断言存在即可锁） | ✅ |

### 反证矩阵（handoff §实施步骤 Step 4 强制实测粘贴）

**反证 1** — 临时注释 `ExamItemsTab.vue:56` try 块 `if (mySeq !== fetchSeq) return`
预期：Test A 红（A 晚到 resolve 覆盖 B，UI 显示 stem-A/99）
实测命令：
```bash
cd /home/ops/projects/edu-cloud-w2/frontend
npx vitest run src/__tests__/knowledge-tree/ExamItemsTab.test.js
```
实测 fail 输出（原样粘贴）：
```
 ❯ src/__tests__/knowledge-tree/ExamItemsTab.test.js (7 tests | 1 failed) 148ms
     × race condition: B resolve → A resolve, UI 停在 B (try guard 锁) 19ms

⎯⎯⎯⎯⎯⎯⎯ Failed Tests 1 ⎯⎯⎯⎯⎯⎯⎯

 FAIL  src/__tests__/knowledge-tree/ExamItemsTab.test.js > ExamItemsTab > race condition: B resolve → A resolve, UI 停在 B (try guard 锁)
AssertionError: expected '共 99 道关联题，显示第 1-10 条单选2019 Astem-A上一页…' to contain 'stem-B'

Expected: "stem-B"
Received: "共 99 道关联题，显示第 1-10 条单选2019 Astem-A上一页1 / 10下一页"

 ❯ src/__tests__/knowledge-tree/ExamItemsTab.test.js:98:18
     96|
     97|     const text = wrapper.text()
     98|     expect(text).toContain('stem-B')
       |                  ^
     99|     expect(text).not.toContain('stem-A')
    100|     expect(text).toContain('11')

 Test Files  1 failed (1)
      Tests  1 failed | 6 passed (7)
```
验证结论：删 try guard → Test A 失败，UI 文本从 B 变为 A (`共 99 道` + `stem-A`)，证明 guard 锁 try 路径 ✅

**反证 2** — 临时注释 `ExamItemsTab.vue:60` catch 块 `if (mySeq !== fetchSeq) return`
预期：Test B 红（A 晚到 reject 清空 items/total，UI 显示空态）
实测命令：
```bash
cd /home/ops/projects/edu-cloud-w2/frontend
npx vitest run src/__tests__/knowledge-tree/ExamItemsTab.test.js
```
实测 fail 输出（原样粘贴）：
```
 ❯ src/__tests__/knowledge-tree/ExamItemsTab.test.js (7 tests | 1 failed) 144ms
     × race condition: B resolve → A reject, UI 停在 B (catch guard 锁) 16ms

⎯⎯⎯⎯⎯⎯⎯ Failed Tests 1 ⎯⎯⎯⎯⎯⎯⎯

 FAIL  src/__tests__/knowledge-tree/ExamItemsTab.test.js > ExamItemsTab > race condition: B resolve → A reject, UI 停在 B (catch guard 锁)
AssertionError: expected '该概念暂无关联高考真题' to contain 'stem-B'

Expected: "stem-B"
Received: "该概念暂无关联高考真题"

 ❯ src/__tests__/knowledge-tree/ExamItemsTab.test.js:123:18
    121|
    122|     const text = wrapper.text()
    123|     expect(text).toContain('stem-B')
       |                  ^
    124|     expect(text).toContain('11')
    125|     // unused hoist to avoid lint (keep 引用)

 Test Files  1 failed (1)
      Tests  1 failed | 6 passed (7)
```
验证结论：删 catch guard → Test B 失败，catch 块 `items.value = []; total.value = 0` 触发，UI 显示 `total===0` 的空态 `该概念暂无关联高考真题`，证明 guard 锁 catch 路径 ✅

**反证 3** — finally 块 `if (mySeq === fetchSeq) loading.value = false`（handoff 预声明 deferred）
预期：非直接锁（loading 状态路径复杂，flakey 风险）
实测：按 handoff §Fix Intent Card 表格 `#3 Pre-declare: finally 守卫由逻辑推理覆盖（A 晚到 finally 把 loading 置 false 时 B 已完成，状态路径次要）` 豁免，不执行

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
| R2-F001 | test-gap | defect_fix | `fetchSeq` guard 无异步竞态 mutant test 锁定；删 `mySeq !== fetchSeq` 早退后 knowledge-tree 156 测全绿 | 2 新 it（resolve race + reject race），deferred promise + setProps 入口；反证 1+2 实测 guard 删除后必红 | ✅ race mutant lock via entry-level DOM assertion | resolved-correct |

### 验证清单自检

- ✅ 设计合规：deferred promise pattern 严格遵守禁忌清单（禁 mockResolvedValue / 禁 setTimeout / 禁断言调用参数）
- ✅ 入口级：`wrapper.setProps({ nodeId })` 通过 Vue 响应式触发 watch → load() → fetchSeq++，非直调 wrapper.vm
- ✅ 断言精准：Test A `toContain('stem-B')` + `not.toContain('stem-A')` + `toContain('11')` + `not.toContain('99')` 4 个；Test B `toContain('stem-B')` + `toContain('11')` 2 个
- ✅ 反证实测粘贴：反证 1+2 完整 fail 输出已入本文件（R2 handoff "未实测"直接教训，不再重犯）
- ✅ ExamItemsTab.vue 零改动：`git diff frontend/src/components/knowledge-tree/ExamItemsTab.vue` 空
- ✅ 白名单 1 文件：`git diff --name-only 80b57fb..121a6c9` = `frontend/src/__tests__/knowledge-tree/ExamItemsTab.test.js`
- ✅ 子集回归：knowledge-tree 14 files / **158 tests PASS** (R2 基线 156 + R3 +2 race mutant，commit 121a6c9 @ 2026-04-18 13:05)
- ✅ 其他红线零触：W1/W3/W4 范围 / master / 后端 `src/edu_cloud/*` / 后端 `tests/test_*` / 其他前端模块 / 任何 CLAUDE.md
- ✅ 派发 handoff §3.1 不写 mini plan（本卡按主 finish-handoff §5 Phase A 步骤 1-8，不要求 mini plan；w2 worktree 派发 handoff-batch3biii §实施步骤 Step 0-7 也未要求）
- ⚠️ 反证 3（finally guard）pre-declared deferred：非直接锁（状态路径复杂，避 flakey）— 与 handoff §Fix Intent Card 反证矩阵表 #3 Pre-declare 一致

### 自查（四要素格式）

#### 边界 case（A 先 resolve / B 先 resolve / A 与 B 几乎同时 resolve）

构造输入: mount nodeId='A' → `setProps({nodeId:'B'})` → resolveB({items:[B1],total:11}) → resolveA({items:[A1],total:99})

运行命令: `cd /home/ops/projects/edu-cloud-w2/frontend && npx vitest run src/__tests__/knowledge-tree/ExamItemsTab.test.js`

实际输出:
```
 ✓ src/__tests__/knowledge-tree/ExamItemsTab.test.js (7 tests) 148ms
   ✓ race condition: B resolve → A resolve, UI 停在 B (try guard 锁)
   ✓ race condition: B resolve → A reject, UI 停在 B (catch guard 锁)
 Test Files  1 passed (1)
      Tests  7 passed (7)
```

结论: 受控 deferred 模式严格锁定 "B 先触发事件 → A 晚到" 的时序。若用户实际场景 A 先 resolve（罕见，nodeId 尚未切换就先 resolve），则 fetchSeq=1===mySeq，guard 不早退，A 数据正常写入——与"B 尚未发出"无冲突。本 Test A/B 只锁"A 晚到不覆盖 B"路径，与 guard 三处（try/catch/finally）职责对齐。A 与 B 几乎同时 resolve 场景 Vue microtask 队列串行消费，仍走 fetchSeq 比较，不存在竞争条件。

#### 状态变量/锁的异常路径（fetchSeq 溢出 / load() 重入）

构造输入: `let fetchSeq = 0` module-scoped；`const mySeq = ++fetchSeq` 入口递增；try/catch/finally 三处 `if (mySeq !== fetchSeq) return`

运行命令: 反证 1 注释 L56 try guard → Test A 红；反证 2 注释 L60 catch guard → Test B 红

实际输出: 见 §反证矩阵（反证 1 Received `共 99 道... stem-A...`；反证 2 Received `该概念暂无关联高考真题`）

结论: 三处 guard 职责分工明确——try 锁旧请求晚到的成功覆盖、catch 锁旧请求晚到的清空触发、finally 锁旧请求晚到把 loading 置 false。反证 1+2 实测证明 try/catch 两处锁生效。finally 处 guard 未做 mutant 实测（派发 handoff §Fix Intent Card 反证矩阵表 #3 明确 pre-declare deferred，理由：finally loading 状态路径次要，mutant flakey）。fetchSeq Number 实际溢出需 2^53 次 load()，前端单会话无风险，不做边界测试。

#### 字符串匹配/条件判断的假阴性（'11'/'99' 被其他 UI 文本误匹配）

构造输入: Test A total=11 → UI "共 11 道关联题" 含 '11'；total=99 → UI "共 99 道关联题" 含 '99'。页码 totalPages = ceil(11/10)=2 或 ceil(99/10)=10，显示 "1 / 2" 或 "1 / 10"，不含 '11' 或 '99'。分页摘要 "第 1-10 条" 不含 '11'/'99'

运行命令: 已包含在反证 1/2 实测中

实际输出: 反证 1 Received `共 99 道关联题，显示第 1-10 条单选2019 Astem-A上一页1 / 10下一页`——`toContain('11')` 在 A 覆盖 B 后 UI 无 '11' 故 fail（隐式经 `toContain('stem-B')` 先 fail 中断）

结论: 断言 'stem-B'（字符串 'stem-B' 是 fixture.stem 唯一子串，UI 无其他 'stem-B' 源）+ '11'（total=11 唯一出现在 "共 N 道" 文本 N 段，totalPages=2 不含 '11'）避免假阴性。`not.toContain('stem-A')` / `not.toContain('99')` 在 A 未覆盖 B 场景下必然成立（UI 文本仅 B 数据）。Test B 反证下 catch 块清空 → UI 文本 "该概念暂无关联高考真题" 不含 'stem-B' 也不含 '11'，断言 fail 精准锁定 catch guard 删除路径。

### 🔀 偏离汇总（审查关注点）

1. **反证 3 未实测**：handoff §Fix Intent Card 反证矩阵 #3 明确 `Pre-declare: finally 守卫由逻辑推理覆盖`，本 R3 遵守，未做 finally mutant 实测。理由同 handoff：finally loading 状态路径次要，mutant test flakey 风险高。
2. **Test B 未加 `not.toContain('stem-A')`**：Test B 反证场景下 A reject 不改 items/total（catch 走 guard 早退），本路径不涉及 A 数据覆盖 B，仅涉及 A reject 是否清空 B。故仅断言 B 存在即可锁 catch 路径。`not.toContain('stem-A')` 非锁定项，省略避免冗余。
3. **`void resolveA` 变量保留**：Test B 用 destructure `resolveA, rejectA, resolveB`，其中 `resolveA` 未调用但保留便于反证 3 potential 扩展；`void resolveA` 避 lint unused-var（已在注释中标明"keep 引用"）。

### 送审准备

1. Baseline: knowledge-tree 子集 14/158 PASS（2026-04-18 13:05）
2. Commit: `121a6c9`（test-only 单 commit）
3. Staged 纯净：`git diff 80b57fb..121a6c9 --name-only` = 1 文件（ExamItemsTab.test.js）
4. Worktree w2 独立（主 wt / W1 / W3 / W4 零相互污染）
5. 下一步: `codex-review code_review_batch3b_iii round=1`（subject_ref `commit:121a6c9`）
6. gates.json R1 回执待写（PASS/FAIL 由 GPT 决，round=1）
7. R1 PASS 后进 Phase B（Batch 3.c T13 + T14 收尾，按主 finish-handoff §5）
8. R1 FAIL → 按 finding 修，R2 FAIL 再拆 3.b.iv（按 gates_lib 硬约束规则）；L015 主动放弃阈值：3 次仍 R2 FAIL → WONTFIX + test_debt TD-004

---

status: submit-for-review-r1
