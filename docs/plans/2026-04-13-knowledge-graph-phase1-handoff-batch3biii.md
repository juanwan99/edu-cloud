<!-- legacy-format -->
---
type: handoff
created: 2026-04-18 09:15:00
project_dir: /home/ops/projects/edu-cloud-w2
design: docs/plans/2026-04-12-knowledge-graph-optimization-design.md
plan: docs/plans/2026-04-13-knowledge-graph-phase1-plan.md
state: docs/plans/2026-04-13-knowledge-graph-phase1-state.json
gates: docs/plans/2026-04-13-knowledge-graph-phase1-gates.json
prev_handoff: docs/plans/2026-04-13-knowledge-graph-phase1-review-handoff-batch3b-r2.md
r2_report: docs/plans/2026-04-13-knowledge-graph-phase1-review-report-batch3b-r2.md
batch: 3.b.iii
batch_scope: R2-F001 单 finding 独立修复 — ExamItemsTab fetchSeq guard 异步竞态 mutant 回归测试补齐
parent_batch_result: code_review_batch3b R2 FAIL (1 HIGH test-gap 剩余)
---

# Batch 3.b.iii 独立修复派发交接卡

## 背景

Batch 3.b R2 codex-review **FAIL**（2026-04-18 08:35，fc4da5f 记录）。R1 5 findings 中 F002/F003/F004/F005 全 resolved-correct；F001 code 修复 resolved-correct，但衍生 **R2-F001 HIGH test-gap**：fetchSeq guard 无异步竞态 mutant test 锁定 — 删 `mySeq !== fetchSeq` 早退后 knowledge-tree 156 测仍全绿。

按 codex-review skill §Gate 条件（R2 FAIL → 拆 topic / WONTFIX，不接受 R3），Planner 决策 = **A 拆子 batch 3.b.iii**（用户 2026-04-18 批准）。

## R2-F001 Finding 摘要（源：R2 report:64-89）

- Severity: **HIGH**
- Category: test-gap
- Type: defect_fix
- Red-flag: ✅ lifecycle / race condition → **requires independent fix design + Semantic Regression Gate**
- Evidence:
  - `frontend/src/components/knowledge-tree/ExamItemsTab.vue:50,56,60,64`（fetchSeq + 3 处 mySeq guard 已落地）
  - `frontend/src/__tests__/knowledge-tree/ExamItemsTab.test.js:40,54`（R2 F002 test 仅覆盖 page/nodeId 不覆盖 race）

## Fix Intent Card（Independent Fix Design）

### Intent
回归测试锁定 fetchSeq guard 行为：**旧请求晚到不覆盖新状态**。仅改测试文件，不触 `.vue` 代码（F001 code 已 R2 resolved-correct）。

### 设计约束（禁止的 fix patterns，源：R2 report:86）
1. ❌ 只断言 `getExamItems` 调用次数/参数（已在 F002 覆盖，不解决 race 锁）
2. ❌ 继续用同步 `mockResolvedValue`（无法制造 race）
3. ❌ 用 `setTimeout` / `sleep` / 定时器碰运气制造竞态（flakey + 非确定性）

### 设计原则（必须的 fix patterns）
1. ✅ 用两个 **deferred promise** 受控挂起 `getExamItems`
2. ✅ 通过 `setProps({ nodeId })` 触发 nodeId 切换（入口级）
3. ✅ 断言**后续 resolve 顺序**与**最终 DOM/state**（而非调用参数）
4. ✅ 覆盖 **resolve race**（try 块守卫）+ **reject race**（catch 块守卫）两条路径

### 测试设计规格（2 新增 it）

**Test A — resolve race: 旧请求 resolve 晚到不覆盖新状态**
```
1. 两个 deferred promise promA / promB
2. getExamItems.mockReturnValueOnce(promA).mockReturnValueOnce(promB)
3. mount nodeId='A' → flushPromises（promA 挂起）
4. setProps nodeId='B' → flushPromises（promB 挂起，此时 fetchSeq=2）
5. resolveB({items:[{id:'B1',stem:'stem-B'}], total:11}) → flushPromises
6. resolveA({items:[{id:'A1',stem:'stem-A'}], total:99}) → flushPromises
7. 断言:
   - wrapper.text() 包含 'stem-B' 且不含 'stem-A'
   - wrapper.text() 包含 '11' 且不含 '99'
```

**Test B — reject race: 旧请求 reject 晚到不清空新状态**
```
1. 两个 deferred promise promA / promB
2. getExamItems.mockReturnValueOnce(promA).mockReturnValueOnce(promB)
3. mount nodeId='A' → flushPromises
4. setProps nodeId='B' → flushPromises（fetchSeq=2）
5. resolveB({items:[{id:'B1',stem:'stem-B'}], total:11}) → flushPromises
6. rejectA(new Error('stale A failed')) → flushPromises
7. 断言:
   - wrapper.text() 包含 'stem-B'（catch 块的 items=[] 若触发则 'stem-B' 会消失）
   - wrapper.text() 包含 '11'（catch 块的 total=0 若触发则 '11' 会消失）
```

### Semantic Regression Gate（反证矩阵 · Executor 必须实测粘贴输出）

| # | 反证操作 | 预期 fail 测试 | 预期 fail 断言 |
|---|---------|-------------|-------------|
| 1 | 删 ExamItemsTab.vue:56 try 块 `if (mySeq !== fetchSeq) return` | Test A resolve race | `wrapper.text()` 变为含 'stem-A' + '99'（A 晚到覆盖 B） → `not.toContain('stem-A')` 红 |
| 2 | 删 ExamItemsTab.vue:60 catch 块 `if (mySeq !== fetchSeq) return` | Test B reject race | `wrapper.text()` items/total 被 A reject 清空为 '' / 0 → `toContain('stem-B')` 或 `toContain('11')` 红 |
| 3 | 删 ExamItemsTab.vue:64 finally 块 `if (mySeq === fetchSeq) loading.value = false` | 非直接锁（loading 状态复杂，避 flakey） | Pre-declare：finally 守卫由逻辑推理覆盖（A 晚到 finally 把 loading 置 false 时 B 已完成，状态路径次要） |

**Executor 必须在审查交接单中粘贴至少反证 1+2 的实测 fail 输出**（R2 handoff §4 "未实测" pre-declare 被 GPT 判 HIGH test-gap 的直接原因）。

## 范围（白名单 1 文件）

| 文件 | 操作 | 说明 |
|------|------|------|
| `frontend/src/__tests__/knowledge-tree/ExamItemsTab.test.js` | MODIFY | +2 it（Test A + Test B），不改已有 5 it |

## 红线（禁改）

- 后端任何文件
- `frontend/src/components/knowledge-tree/ExamItemsTab.vue`（F001 code 已 R2 resolved-correct，**严禁重修**）
- `frontend/src/__tests__/knowledge-tree/` 其他测试文件（F002/F003/F004 已 R2 resolved）
- `frontend/src/components/knowledge-tree/TreeNavPanel.vue` / `StudyUnitTab.vue`（F003/F004/F005 已 R2 resolved）
- `frontend-nuxt/*`（W3 范围）/ `src/edu_cloud/modules/card/*`（W1）/ `conduct/*`（W4）
- 任何 CLAUDE.md 同步（纯测试增量，doc_sync_guard 不触发）

## 实施步骤

```bash
cd /home/ops/projects/edu-cloud-w2

# Step 0: 起点验证
git log --oneline -3  # 应见 fc4da5f (R2 FAIL report) / 9844199 / 317dfb6
git status            # working tree 应净（只有 node_modules untracked）

# Step 1: 读 ExamItemsTab.vue 确认 fetchSeq pattern 仍是 3 处 guard
grep -n "mySeq !== fetchSeq\|mySeq === fetchSeq" frontend/src/components/knowledge-tree/ExamItemsTab.vue

# Step 2: 补 Test A + Test B（精读 Fix Intent Card §测试设计规格）
# 不要用 mockResolvedValue！必须 deferred promise pattern

# Step 3: 子集 verify — 期望 156 → 158 PASS（+2）
cd frontend && npx vitest run src/__tests__/knowledge-tree/ExamItemsTab.test.js 2>&1 | tail -10
cd frontend && npx vitest run src/__tests__/knowledge-tree/ 2>&1 | tail -5

# Step 4: 反证实测（Semantic Regression Gate 强制）
# 反证 1: 注释掉 ExamItemsTab.vue:56 的 `if (mySeq !== fetchSeq) return` → 跑 Test A → 必红 → 粘贴 fail 输出
# 反证 2: 注释掉 ExamItemsTab.vue:60 的 `if (mySeq !== fetchSeq) return` → 跑 Test B → 必红 → 粘贴 fail 输出
# 每次反证完必须恢复原文件（git diff 核对零残留）

# Step 5: commit
# `test(frontend): R3 R2-F001 ExamItemsTab race mutant test (kg-phase1 batch 3.b.iii)`

# Step 6: 审查交接单
# 写 docs/plans/2026-04-13-knowledge-graph-phase1-review-handoff-batch3biii.md
# 包含: subject_ref + Fix Card 行 + 反证实测粘贴输出 + 验证清单

# Step 7: commit 审查交接单后触发 codex-review
export AIPROXY_OAI_KEY="$(cat ~/.secrets/aiproxy.key)"
# 调 codex-review code_review_batch3b_iii round=1
```

## 验收契约

- ✅ Test A + Test B PASS（knowledge-tree 子集 156 → 158）
- ✅ 反证 1+2 实测 fail 输出粘贴到审查交接单（R2-F001 直接教训）
- ✅ 不触红线文件（`git diff --cached --name-only` = 白名单 1 文件 + handoff 文档）
- ✅ ExamItemsTab.vue 零改动（反证结束必 `git diff frontend/src/components/knowledge-tree/ExamItemsTab.vue` → 空）
- ✅ codex-review `code_review_batch3b_iii` R1 PASS（R1 不满足 R2 升级条件 → 若 R2 仍 FAIL 按 skill 规则再拆 3.b.iv 或 WONTFIX）

## checkpoint 输出格式

```
【Batch 3.b.iii 修复 · 待汇总】
- 工作分支：feat/kg-batch3b
- R3 commit：<sha>（test-only）
- vitest：158 passed / 0 failed（+2 race mutant）
- 反证实测：1+2 fail 输出已粘贴到 review-handoff
- codex-review task ID：<id>，结果：PASS/FAIL
- 异常：<列出>
- 等 T2 汇总（W2 partial-merge）
```

## 兜底

- deferred promise pattern 不熟 → 参照 vitest 官方文档 `new Promise((resolve, reject) => {...})` + 将 resolver 暴露到外层变量
- Test A/B 首跑即绿但反证后仍绿 → 说明 mock 接线错误（可能 mockReturnValueOnce 顺序 / flushPromises 不够），**不要**改 ExamItemsTab.vue，重审 test mock pattern
- 修 ≥3 次仍 R2 FAIL → L015 主动放弃 → 触发 WONTFIX + Contract Pack test_debt TD-004

## 与其他窗口同步

- 零文件冲突（W1/W3/W4 红线互斥）
- 不直接 commit master
- W2 Batch 3.b.iii PASS 后由 T2-补遗 session merge 到 master（与 Batch 3.b R2 已修复的 `66ab2b8..317dfb6` 一起合批）

## 第一步指令

```bash
cd /home/ops/projects/edu-cloud-w2
cat docs/plans/2026-04-13-knowledge-graph-phase1-review-report-batch3b-r2.md  # 必读 R2 report R2-F001 全文
cat docs/plans/2026-04-13-knowledge-graph-phase1-handoff-batch3biii.md  # 必读本卡
git log --oneline -3
git status
# 报告："已读 R2-F001 + Fix Intent Card，进入 Step 1 ExamItemsTab.vue fetchSeq pattern 确认"
```

---

status: dispatched-for-executor-r3
