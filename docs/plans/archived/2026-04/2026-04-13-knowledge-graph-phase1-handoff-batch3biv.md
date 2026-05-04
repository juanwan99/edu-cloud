<!-- legacy-format -->
---
type: handoff
created: 2026-04-18 13:30:00
project_dir: /home/ops/projects/edu-cloud-w2
design: docs/plans/2026-04-12-knowledge-graph-optimization-design.md
plan: docs/plans/2026-04-13-knowledge-graph-phase1-plan.md
state: docs/plans/2026-04-13-knowledge-graph-phase1-state.json
gates: docs/plans/2026-04-13-knowledge-graph-phase1-gates.json
prev_handoff: docs/plans/2026-04-13-knowledge-graph-phase1-review-handoff-batch3biii.md
r1_report: docs/plans/2026-04-13-knowledge-graph-phase1-review-report-batch3biii.md
batch: 3.b.iv
batch_scope: R3-F001 单 finding 独立修复 — ExamItemsTab fetchSeq finally guard 异步竞态 mutant 回归测试补齐
parent_batch_result: code_review_batch3b_iii R1 FAIL (1 HIGH test-gap 剩余，派发 handoff §Fix Intent Card #3 pre-declare 漏洞)
---

# Batch 3.b.iv 独立修复派发交接卡

## 背景

Batch 3.b.iii R1 codex-review **FAIL**（2026-04-18 13:14，`e5dca4d` 记录）。R3 Test A/B 已锁 try/catch guard，但 **R3-F001 HIGH test-gap**：finally guard（`ExamItemsTab.vue:64` `if (mySeq === fetchSeq) loading.value = false`）未被 mutant 锁定。GPT 独立 mutant 路径：删 guard 成无条件 `loading.value = false` → 158 测仍全绿。

Batch 3.b.iii R1 FAIL 的 pre-declare 漏洞根因：派发 handoff §Fix Intent Card #3 的理由「A 晚到 finally 把 loading 置 false 时 B 已完成」仅覆盖 **"A 晚到 == B 已完成"** 单一场景，不涵盖 **"A 先 settle / B 仍 pending"** 另一条路径。此场景下 finally guard 专属锁 loading（try/catch guard 均不生效，因为 try/catch 走 `return` 早退不会接触 loading）。

按 codex-review skill §Gate 条件（R2 条件不满足 → 拆 topic），**用户 2026-04-18 13:28 批准 Option A 拆子 batch 3.b.iv**。

## R3-F001 Finding 摘要（源：R1 report:53-66）

- Severity: **HIGH**
- Category: test-gap
- Type: defect_fix
- Red-flag: ✅ lifecycle / race condition → **requires independent fix design + Semantic Regression Gate**
- Evidence:
  - `frontend/src/components/knowledge-tree/ExamItemsTab.vue:64`（finally guard 三处之一）
  - `frontend/src/__tests__/knowledge-tree/ExamItemsTab.test.js:79`（Test A 只锁 try guard）
  - `frontend/src/__tests__/knowledge-tree/ExamItemsTab.test.js:104`（Test B 只锁 catch guard）

## Fix Intent Card（Independent Fix Design）

### Intent

回归测试锁定 `finally` guard 行为：**旧请求先 settle 时，loading 不被提前关闭**。仅改测试文件，不触 `.vue` 代码（F001 code 已 R2 resolved-correct，R3 已复核）。

### 设计约束（禁止的 fix patterns，源：R1 report:71）

1. ❌ 把 "B 已完成" 的场景当作 finally 代理（这正是 3.b.iii Test A/B 已覆盖的路径，与 finally 无关）
2. ❌ 继续用同步 `mockResolvedValue`（无法制造 "A 先 settle, B pending" 时序）
3. ❌ 用 `setTimeout` / `sleep` / 定时器伪造竞态（flakey + 非确定性）
4. ❌ 只断言 `loading.value` 内部 state（应断言 DOM "加载中…" 文本，入口级）

### 设计原则（必须的 fix patterns）

1. ✅ 用两个 **deferred promise** 受控挂起 `getExamItems`
2. ✅ 通过 `setProps({ nodeId })` 触发 nodeId 切换（入口级）
3. ✅ **关键时序差异**：与 3.b.iii Test A/B 相反——**resolveA 先发生，而 resolveB 故意不触发**（B 仍 pending）
4. ✅ 断言此时 DOM 文本仍含 `'加载中'`（finally guard 保持 loading=true）
5. ✅ 最后 resolveB → 断言 DOM 切到 B 数据 + loading=false

### 测试设计规格（1 新增 it）

**Test C — finally guard: 旧请求先 settle 时新请求仍 pending, UI 保持 loading**

```
1. 两个 deferred promise promA / promB
2. getExamItems.mockReturnValueOnce(promA).mockReturnValueOnce(promB)
3. mount nodeId='A' → flushPromises（promA 挂起，fetchSeq=1）
4. setProps nodeId='B' → flushPromises（promB 挂起，fetchSeq=2，loading=true）
5. resolveA({items:[...], total:99}) → flushPromises
   - A 的 try guard: mySeq=1 !== fetchSeq=2 → return, items/total 不被覆盖
   - A 的 finally guard: mySeq=1 !== fetchSeq=2 → loading 不被改
6. 断言 UI 仍在 loading 态:
   - wrapper.text() 包含 '加载中'
   - wrapper.text() 不含 'stem-A'（try guard 生效）
7. resolveB({items:[{id:'B1',stem:'stem-B'}], total:11}) → flushPromises
   - B 的 finally guard: mySeq=2 === fetchSeq=2 → loading=false
8. 断言 UI 切到 B:
   - wrapper.text() 包含 'stem-B'
   - wrapper.text() 不含 '加载中'
```

### Semantic Regression Gate（反证矩阵 · Executor 必须实测粘贴输出）

| # | 反证操作 | 预期 fail 测试 | 预期 fail 断言 |
|---|---------|-------------|-------------|
| 1 | 删 `ExamItemsTab.vue:64` finally 块 `if (mySeq === fetchSeq) loading.value = false` → 改为无条件 `loading.value = false` | Test C 步骤 6 | A resolve 后 finally 直接 `loading=false` → `v-else-if total===0` → UI 显示「该概念暂无关联高考真题」→ `toContain('加载中')` 红 |
| 2 | 确认本反证与 3.b.iii 反证 1+2 正交：删 try guard 本 Test C 步骤 6 `not.toContain('stem-A')` 红（已由 3.b.iii Test A 覆盖），非 finally 专属 | — | Pre-declare：finally 专属锁通过反证 #1 证明 |

**Executor 必须在审查交接单中粘贴反证 #1 的实测 fail 输出**（3.b.iii R1 FAIL 直接教训：pre-declare 不能替代实测）。

## 范围（白名单 1 文件）

| 文件 | 操作 | 说明 |
|------|------|------|
| `frontend/src/__tests__/knowledge-tree/ExamItemsTab.test.js` | MODIFY | +1 it（Test C），不改已有 7 it（基础 3 + F002 2 + R3 race 2） |

## 红线（禁改）

- 后端任何文件
- `frontend/src/components/knowledge-tree/ExamItemsTab.vue`（F001 code 已 R2 resolved-correct，反证后必 git diff 零残留，**严禁 commit 任何 .vue 修改**）
- `frontend/src/__tests__/knowledge-tree/` 其他测试文件
- `frontend/src/components/knowledge-tree/` 其他 .vue
- `frontend-nuxt/*`（W3 范围）/ `src/edu_cloud/modules/card/*`（W1）/ `conduct/*`（W4）
- master / W1 / W3 / W4 worktree
- 任何 CLAUDE.md 同步（纯测试增量，doc_sync_guard 不触发）

## 实施步骤

```bash
cd /home/ops/projects/edu-cloud-w2

# Step 0: 起点验证
git log --oneline -3  # 应见 e5dca4d (R1 FAIL report) / ad7e957 / 121a6c9
git status            # working tree 应净（只有 node_modules + .codex-code-review-raw.log）

# Step 1: 读 ExamItemsTab.vue 确认 finally guard pattern
grep -n "mySeq === fetchSeq\|loading.value = false" frontend/src/components/knowledge-tree/ExamItemsTab.vue
# 应见 L64 `if (mySeq === fetchSeq) loading.value = false`

# Step 2: 补 Test C（精读 Fix Intent Card §测试设计规格）
# 不要用 mockResolvedValue！必须 deferred promise pattern
# 不要断言 wrapper.vm.loading.value！必须 wrapper.text() DOM 入口

# Step 3: 子集 verify — 期望 158 → 159 PASS（+1）
cd frontend && npx vitest run src/__tests__/knowledge-tree/ExamItemsTab.test.js 2>&1 | tail -10
cd frontend && npx vitest run src/__tests__/knowledge-tree/ 2>&1 | tail -5

# Step 4: 反证 #1 实测（Semantic Regression Gate 强制）
# 反证 1: 注释掉 ExamItemsTab.vue:64 的 `if (mySeq === fetchSeq)`
#   并把 loading.value = false 保留（变成无条件赋值）
# 跑 Test C → 必红 → 粘贴 fail 输出
# 反证完必须恢复原文件（git diff ExamItemsTab.vue 零残留）

# Step 5: commit
# `test(frontend): R4 R3-F001 ExamItemsTab finally guard race mutant test (kg-phase1 batch 3.b.iv)`

# Step 6: 审查交接单
# 写 docs/plans/2026-04-13-knowledge-graph-phase1-review-handoff-batch3biv.md
# 必需 sections: 逐 Task 自审 / 反证矩阵（粘贴反证 #1 实测 fail）/ 自查（四要素）/ Fix Card / 验证清单

# Step 7: commit 审查交接单后触发 codex-review
export AIPROXY_OAI_KEY="$(cat ~/.secrets/aiproxy.key)"
# 调 codex-review code_review_batch3b_iv round=1
```

## 验收契约

- ✅ Test C PASS（knowledge-tree 子集 158 → 159）
- ✅ 反证 #1 实测 fail 输出粘贴到审查交接单
- ✅ 不触红线文件（`git diff 80b57fb..HEAD --name-only` 白名单：3.b.iii 1 文件 + 3.b.iv 1 文件 + 相关 handoff/report docs）
- ✅ ExamItemsTab.vue 零改动（反证结束必 `git diff frontend/src/components/knowledge-tree/ExamItemsTab.vue` → 空）
- ✅ codex-review `code_review_batch3b_iv` R1 PASS（R2 升级条件仍不满足：T3/单文件/非 remote-deploy；R1 FAIL 再拆 3.b.v 或 WONTFIX）

## checkpoint 输出格式

```
【Batch 3.b.iv 修复 · 待汇总】
- 工作分支：feat/kg-batch3b
- R4 commit：<sha>（test-only）
- vitest：159 passed / 0 failed（+1 finally race mutant）
- 反证 #1 实测：fail 输出已粘贴到 review-handoff-batch3biv
- codex-review task ID：<id>，结果：PASS/FAIL
- 异常：<列出>
- 等 T2 汇总（W2 partial-merge）
```

## 兜底

- deferred promise pattern 不熟 → 参照 3.b.iii Test A/B 代码（同 pattern，仅时序差异）
- Test C 首跑即红 → 先跑基础测再补 Test C（不要改 .vue）
- Test C 首跑即绿但反证后仍绿 → 说明 mock 接线错误（可能 mockReturnValueOnce 顺序 / flushPromises 不够），**不要**改 ExamItemsTab.vue，重审 test mock pattern
- 修 ≥3 次仍 R1 FAIL → L015 主动放弃 → 触发 WONTFIX + Contract Pack test_debt TD-004（需 Planner 签字）

## 与其他窗口同步

- 零文件冲突（W1/W3/W4 红线互斥）
- 不直接 commit master
- W2 Batch 3.b.iv PASS 后由 T2-补遗 session 一并 merge 到 master（与 3.b R2 已修复的 `66ab2b8..317dfb6` + 3.b.iii 的 `121a6c9..ad7e957` 合批）

## 第一步指令

```bash
cd /home/ops/projects/edu-cloud-w2
cat docs/plans/2026-04-13-knowledge-graph-phase1-review-report-batch3biii.md  # 必读 R1 FAIL report R3-F001 全文
cat docs/plans/2026-04-13-knowledge-graph-phase1-handoff-batch3biv.md         # 必读本卡
git log --oneline -3
git status
# 报告："已读 R3-F001 + Fix Intent Card，进入 Step 1 ExamItemsTab.vue finally guard pattern 确认"
```

---

status: dispatched-for-executor-r4
