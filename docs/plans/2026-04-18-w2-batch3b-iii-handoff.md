<!-- legacy-format -->
# T-D · W2 kg-phase1 Batch 3.b.iii · race mutant test 补丁 · 执行交接卡

> 类型：Gate 2 R2 FAIL → 拆新 batch（不接受 R3）
> 创建：2026-04-18 规划窗口（Opus 4.7）
> 工作分支：`feat/kg-batch3b`（继续，不另开分支）
> 工作 worktree：**`/home/ops/projects/edu-cloud-w2`**
> 起点 HEAD：`fc4da5f`（R2 FAIL review report）
> 用户决策：选项 1 拆 batch 3.b.iii（2026-04-18，规划窗口推荐）

## 1. 触发背景
- Batch 3.b R2 结果 FAIL @ `fc4da5f`：4/5 R1 finding resolved-correct + 1 衍生 R2-F001 HIGH test-gap
- gates_lib 硬约束：R2 FAIL → raise ValueError 拒绝 R3（防 R3+ 退化为 patch 循环）
- 选项 4 (推后 3.c 合并修) 拒绝原因：Batch 3.c 启动 ETA 未知 + 范围蔓延

## 2. R2-F001 详情（GPT 原话）
> fetchSeq guard 无异步竞态 mutant test 锁。要求：用 2 个受控 Promise（deferred）mock `getExamItems`，A 先挂起 + B 触发切换，断言"B resolve → A resolve" 与 "B reject → A resolve" 两路径下 UI 停在 B。**禁 mockResolvedValue 同步 / 禁 sleep 伪造竞态**。

## 3. R8 ⚠️ 不，这是 Batch 3.b.iii 任务清单

### 3.1 必做 · 写 mini plan
- 文件：`docs/plans/2026-04-18-kg-batch3b-iii-plan.md`（≤200 行）
- 内容必须包含：
  - frontmatter（type=plan, topic=kg-batch3b-iii, T-level=T2, gates 引用）
  - 1 个 Task：补 ExamItemsTab race mutant test
  - 测试契约：deferred Promise 协议 + 2 路径断言 + mutant verify 步骤
  - Contract Pack：1 invariant（"fetchSeq guard 必须在 race 下保护 UI"）+ 1 counter_example（"删除 fetchSeq guard，race test 必须红"）

### 3.2 必做 · 补 race mutant test
- 文件：`frontend/src/__tests__/knowledge-tree/ExamItemsTab.test.js`
- 新增 2 个 case：
  - `race condition: B resolve → A resolve, UI 停在 B`
  - `race condition: B reject → A resolve, UI 停在 B（但 A 数据被 fetchSeq 拒）`
- 实现要点（防伪造）：
  ```js
  let resolveA, resolveB;
  const promiseA = new Promise(r => { resolveA = r; });
  const promiseB = new Promise(r => { resolveB = r; });
  vi.mocked(getExamItems).mockImplementationOnce(() => promiseA);
  vi.mocked(getExamItems).mockImplementationOnce(() => promiseB);
  // 触发 A，prop 变化触发 B（fetchSeq++）
  // resolve B 先 → resolve A 后
  // 断言 wrapper 显示 B 数据，A 数据被 guard 拒
  ```

### 3.3 必做 · mutant verify
- 注释 ExamItemsTab.vue 中 fetchSeq guard（保留 load 函数其他逻辑）
- 跑新 race test → **必须红**（否则证明测试无锁定能力）
- 恢复 guard，跑新 race test → **必须绿**

### 3.4 必做 · 触发 codex-review
```bash
cd /home/ops/projects/edu-cloud-w2
export AIPROXY_OAI_KEY="$(cat ~/.secrets/aiproxy.key)"
# 调 codex-review code_review_batch3b_iii round=1
```

## 4. 范围定义

### 4.1 可改文件（白名单）
- `frontend/src/__tests__/knowledge-tree/ExamItemsTab.test.js`（加 2 race case）
- `docs/plans/2026-04-18-kg-batch3b-iii-plan.md`（新建 mini plan）
- `docs/plans/2026-04-18-kg-batch3b-iii-gates.json`（新建 gates，仅 code_review_batch3b_iii 一项）

### 4.2 红线禁区（绝对不能碰）
- `frontend/src/components/knowledge-tree/ExamItemsTab.vue`（fetchSeq guard 已 R2 PASS 不动）
- 其他 R1/R2 已 resolved 文件（TreeNavPanel.vue / StudyUnitTab.vue 等）
- W1/W3/W4 范围
- master / 其他 worktree

## 5. 验收契约
- mini plan 文件落盘 ≤200 行
- ExamItemsTab.test.js 含 2 个新 race case，mutant verify 通过（注释 guard 必红）
- vitest 子集 PASS（不破坏现有 153 + 5 R2 修复）
- codex-review code_review_batch3b_iii R1 PASS

## 6. checkpoint 输出格式
```
【T-D batch 3.b.iii · 待汇总】
- 工作分支：feat/kg-batch3b @ <最终 sha>
- mini plan：docs/plans/2026-04-18-kg-batch3b-iii-plan.md（N 行）
- 新增 race test：2 cases
- mutant verify：注释 guard → race test N 个红 / 恢复 guard → 全绿
- vitest 子集：N passed / 0 failed
- codex-review code_review_batch3b_iii R1：PASS / FAIL（FAIL 则进 R2 修复或拆 3.b.iv）
- 等 T2-补遗-1 merge feat/kg-batch3b 到 master（PASS 后）
```

## 7. 与其他窗口同步
- W4-R8 / T-C T2-Partial / B1 视觉验收 都不依赖本任务
- 本任务完成不立即 merge master，等用户决策 T2-补遗-1
- 不动 W1/W3/W4 worktree

## 8. 启动 prompt（W2 worktree 新 session）
```
继续 kg-phase1 Batch 3.b.iii — race mutant test 补丁。

工作目录：/home/ops/projects/edu-cloud-w2
工作分支：feat/kg-batch3b @ fc4da5f
依据交接卡：/home/ops/projects/edu-cloud-t2/docs/plans/2026-04-18-w2-batch3b-iii-handoff.md
依据 R2 FAIL 报告：docs/plans/2026-04-13-knowledge-graph-phase1-review-report-batch3b-r2.md（W2 worktree fc4da5f）

T2 任务（不动 ExamItemsTab.vue，仅补测试）。第一步：
1. verify HEAD = fc4da5f + working tree clean
2. 读交接卡 §3 任务清单
3. 先写 mini plan（§3.1）报告等用户确认
4. 再开 race test 实现（§3.2）+ mutant verify（§3.3）
5. 触发 codex-review（§3.4）

GPT 关键约束：禁 mockResolvedValue 同步 / 禁 sleep 伪造竞态，用 2 个 deferred Promise。
```

## 9. 兜底
- mini plan 写出来后 GPT plan review FAIL → 按反馈修订（小 plan 应该 1-2 轮过）
- race test 写不出 deferred 模式 → 输出"超出能力边界" + 调用 Codex 协助
- code_review_batch3b_iii R1 又 FAIL → 按 R1 finding 修，R2 FAIL 再拆 3.b.iv（按 gates_lib 硬约束规则）
