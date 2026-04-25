---
type: planner-handoff
created: 2026-04-14 12:15:00
project_dir: C:\Users\Administrator\edu-cloud
design: C:\Users\Administrator\edu-cloud\docs\plans\2026-04-12-knowledge-graph-optimization-design.md
plan: C:\Users\Administrator\edu-cloud\docs\plans\2026-04-13-knowledge-graph-phase1-plan.md
state: C:\Users\Administrator\edu-cloud\docs\plans\2026-04-13-knowledge-graph-phase1-state.json
gates: C:\Users\Administrator\edu-cloud\docs\plans\2026-04-13-knowledge-graph-phase1-gates.json
prev_batch_handoff: C:\Users\Administrator\edu-cloud\docs\plans\2026-04-13-knowledge-graph-phase1-handoff-batch3b.md
topic: 2026-04-13-knowledge-graph-phase1
tier: T3
---

# Planner → Planner 交接（规划窗口交接文档）

## 用途

本文件写给**下一个接手 kg-phase1 的 Planner 会话**。上一轮 Planner 完成了 Batch 3.a 的 Gate 2 R2 PASS 闭环 + Batch 3.b 交接卡派发，但因 Executor 新会话尚未启动（或启动后尚未返回），Planner 挂起。下一位 Planner 接过规划把手继续推进。

## 当前门控全态（2026-04-14 12:15 verified）

| Gate | Status | 锚点 |
|------|--------|------|
| `plan_review` | ✅ pass | subject_hash `a963e85b...` (plan.md @ db413f2, R6 PASS) |
| `code_review_batch1` (T1-T6) | ✅ pass | commits `1c3c1a2..bcb1971` |
| `code_review_batch2` (T7-T8) | ✅ pass | commit `d300263` |
| `code_review_batch3a` (T9-T10) | ✅ pass (R2) | commits `2ab10a2..c5bff80` |
| `code_review_batch3b` (T11-T12) | ⏸ 未创建 | 待 Executor 完成后由 codex-review 写回执 |
| `code_review_batch3c` (T13-T14) | ⏸ 未创建 | 待 Batch 3.b PASS 后推 |

Task 矩阵（state.json）：T0-T10 completed，T11-T14 pending。

## 下一位 Planner 启动清单（按顺序）

### Step 1: 检查 Batch 3.b Executor 是否启动/完成

```bash
cd C:/Users/Administrator/edu-cloud && git log --oneline f9ab3a1..HEAD
ls docs/plans/2026-04-13-knowledge-graph-phase1-review-handoff-batch3b.md 2>&1
ls docs/plans/2026-04-13-knowledge-graph-phase1-review-report-batch3b*.md 2>&1
```

**四种情形**：

**情形 A — Executor 尚未启动**（HEAD 仍为 `f9ab3a1`，无 review-handoff-batch3b 文件）:
- Planner 等候，向用户复述 Batch 3.b 启动 Prompt（见 handoff-batch3b.md 末尾）
- 不主动 Edit 代码，保持挂起

**情形 B — Executor 在途**（有 T11/T12 commit，但无 review-handoff-batch3b）:
- Executor 新会话正在执行，Planner 继续挂起
- 建议不 push 到远端，避免污染 diff

**情形 C — Executor 完成，等 Gate 2 审查**（有 review-handoff-batch3b 文件 + commits，但无 review-report-batch3b）:
- Planner 触发 codex-review skill（code_review 模式）跑 Gate 2 R1
- 参数：subject commits（T11/T12 commit 范围）+ review-handoff 文件

**情形 D — Gate 2 已有结果**（有 review-report-batch3b.md）:
- 读报告判定 PASS / FAIL
- PASS → 推 Batch 3.c
- FAIL → 按 finding 分类（code-bug/test-gap 必修；behavior_change 必须用户单独确认）生成 R2 指令，可能扩容 scope

### Step 2: Batch 3.b 验收决策（情形 C/D 适用）

Gate 2 判定按 `~/.claude/rules-t3/review-templates.md <!-- anchor: pass-fail -->`：
- code-bug / test-gap 的 HIGH/MED 未修复 → FAIL
- 每批最多 3 轮，R3 仍 FAIL 按 "FAIL 升级" 分类处置

### Step 3: 推 Batch 3.c（Batch 3.b PASS 后）

**Batch 3.c 范围**（T13 + T14）：

| Task | 内容 | 文件 |
|------|------|------|
| T13 | `ModuleOverviewPanel.vue` 追加 stats_overview prop + freqDist + coverage%；KnowledgeTreePage.vue 传 :stats-overview；useKnowledgeTree.js 新增 loadStatsOverview | 3 改 + 1 新增测试 |
| T14 Step 0 | **P001 处置**（INV-002）：新增 `test_exam_frequency_l1_set_equals_kb_l1` controlled fixture，schema `concepts + diagnostic_attributes + q_matrix` | 1 文件 |
| T14 Step 1-4 | Phase 1 收尾：design.md 头部 `[实现完成]` 标记 + 审查交接单 + commit | 2 文件（design.md + review handoff） |

**注意**：T14 Step 0 的 fixture schema 已在 plan R6 明确——**3 张表 `concepts + diagnostic_attributes + q_matrix`**（R5-T001 修复已锁定）。Executor 按 plan 照做即可，**不要自行增加 `assessment_items` 或 `da_knowledge_point_map`**。

**Phase 1 收尾 T14 额外工作**（不在 plan Steps 里但 Planner 必做）：
- 将全局 CLAUDE.md「进行中设计」的 kg-phase1 条目**迁移到「已完成设计」段**
- 将 edu-cloud/CLAUDE.md「参考文档」段**追加** kg-phase1 条目（格式参照其他已完成 Phase）
- 全局 CLAUDE.md 「最近 sync 落盘记录」追加 kg-phase1 Phase 1 实现完成条目

### Step 4: P001 闭环验证

P001 的两个半 finding（INV-002 + INV-004）处置策略：

| 半 finding | Batch 3.c 落地方式 | 状态 |
|-----------|------------------|------|
| INV-002 L1 集合相等 | T14 Step 0 新增测试 `test_exam_frequency_l1_set_equals_kb_l1`，controlled fixture + 3 类 mutant 反证 | 📝 plan R6 已定义，待落盘 |
| INV-004 前端契约 | TreeNavPanel.test.js (T12) + ModuleOverviewPanel.test.js (T13) 组件级断言 | 📝 待 Batch 3.b/3.c 落盘 |
| INV-004 KnowledgeTreePage 集成 | **deferred Phase 2 (deadline 2026-05-31)** — 子组件 stub 不证明契约 | ⏸ 已接受延期 |

Batch 3.c PASS 后确认 INV-002 / INV-004 的 verification 映射全部指向真实落盘测试（无"承诺未实现"债务）。

## 上轮 Planner 会话核心教训（必须规避）

### L-KG-3a-1: Planner 必须独立核查代码，不信 Executor 单方 scope 分析

**事故**：Batch 3.a R1 FAIL 后，Executor 在 review-report 的"R2 处置建议"段判断 "F001 修复要触 `useKnowledgeTree.js`（handoff 严禁修改）"。上轮 Planner **独立读 useKnowledgeTree.js:81** 发现 `selectedStudentId` 已经导出，Executor 漏看了这一行。F001 修复**完全在 scope 内**（只改 KnowledgeTreePage.vue 页面解构）。

**教训**：收到 Executor 的 FAIL 报告后，每个 finding 的 scope 结论都要 Planner 独立 grep/read 代码再判定。Executor 可能没有把相关代码查全。

**适用**：Batch 3.b / 3.c 收到 Executor R2 指令分析时，Planner 不直接采纳 scope 结论，必须验证每个修复点涉及的真实代码位置。

### L-KG-3a-2: staging 污染 → R4 PASS 幽灵 hash

**事故**：R4 Plan Review 跑在 working directory（当时有未 commit 的 F010/INV-005 改动），PASS 后 gates.json 锁定了 working dir 的 file hash `94cb65d7`，**该 hash 不匹配任何 commit**。后续 R3 修订 commit 时 `git add plan.md` 把幽灵改动一起 commit，导致 R5 误判为"超范围 amendment"。

**教训**：
1. Plan Review / Code Review 跑前必须 `git status` 确认 plan.md 为 clean（无未 commit 改动），否则 PASS 后 gates.json 会锁定幽灵 hash
2. commit 前必须 `git diff --cached --name-only` 确认 staging 只含本次意图的文件，发现夹带改动 → `git reset HEAD <file>` 清理后重新精确 add
3. codex-review skill 的 write_receipt 用的是**磁盘 file hash**（`gates_lib.compute_file_hash`），不是 git object hash——working dir 和 HEAD 不一致时会写入磁盘版本的 hash

**适用**：Batch 3.c T14 Step 0 和收尾 commit 前必须 `git status + git diff --cached --name-only` 双查。

### L-KG-3a-3: Gate 1 再审的触发条件

**事故**：上轮 Planner 第一次声明"不必补跑 Plan Review R5"（因为 P001 R3 修订"仅文档同步"）。但 session_guard 基于 file hash 判断，只要 plan.md 变了就 block executing-plans skill，实际被迫跑 R5 → FAIL → R6。

**教训**：plan.md 文件任何修改都会触发 hash 失配。Planner 修 plan 时必须同时决策是否跑新一轮 Plan Review：
- **必须跑新一轮**：修 Task 内容 / 修 invariants / 修 verification 映射 / 修测试契约
- **可以跳过**（但要承担风险）：修 typo / 修 freshness / 修注释行

文档修订后如果选"跳过"，要预期 codex-review 下次调用会触发 session_guard block，必须手动更新 gates.json.subject_hash（但这要 GPT 独立验证背书，否则审查机制失效）。

**适用**：Batch 3.c T14 Step 0 的 plan 修订（如果需要）+ P001 处置修订都要考虑是否触发新一轮 Plan Review。

### L-KG-3a-4: Tier 必须在会话开始就声明

**事故**：上轮 Planner 会话开始时未在 CLAUDE.md 或 SessionState 声明 T3 tier，导致 session_guard block 调用 codex-review skill（"当前 tier=None"）。需要手动跑脚本写 `SessionState.effective_tier='T3'` 才能继续。

**教训**：新 Planner 会话开始，立即在首次文本输出声明 `[T3] {描述} — 判据`。若调用 Skill 前 hook 报 tier=None，用 `python -c "import sys; sys.path.insert(0, 'C:/Users/Administrator/.claude/hooks'); import hook_lib; ss = hook_lib.SessionState('<session-id>'); ss.write('declared_tier', 'T3'); ss.write('effective_tier', 'T3')"` 补写。

**适用**：下一位 Planner 会话开始立即声明 T3，免得中途被 hook block。

## 关键文件路径速查

| 用途 | 绝对路径 |
|------|---------|
| 设计文档 | `C:\Users\Administrator\edu-cloud\docs\plans\2026-04-12-knowledge-graph-optimization-design.md` |
| Plan (R6) | `C:\Users\Administrator\edu-cloud\docs\plans\2026-04-13-knowledge-graph-phase1-plan.md` |
| Plan Review R6 报告 | `C:\Users\Administrator\edu-cloud\docs\plans\2026-04-13-knowledge-graph-phase1-plan-review-r6.md` |
| Gates 回执 | `C:\Users\Administrator\edu-cloud\docs\plans\2026-04-13-knowledge-graph-phase1-gates.json` |
| State | `C:\Users\Administrator\edu-cloud\docs\plans\2026-04-13-knowledge-graph-phase1-state.json` |
| Batch 3.a R2 PASS 报告 | `docs/plans/2026-04-13-knowledge-graph-phase1-review-report-batch3a-r2.md` |
| Batch 3.b 交接卡 | `docs/plans/2026-04-13-knowledge-graph-phase1-handoff-batch3b.md` |

## 测试基线（2026-04-14 12:15 verified）

| 层 | 基线 |
|----|------|
| 前端 Vitest 全量 | 24 files / 233 tests PASS（Batch 3.a R2 闭环） |
| 后端 knowledge_tree 子集 | 160 tests PASS |
| 后端 stats_service | 13 tests PASS |

Batch 3.b 完成后期望：前端 ~253 tests（新增 ~20）。Batch 3.c T14 Step 0 后新增 1 后端 test。

## 环境 / 流程约束

- session_guard 会校验 plan.md hash 与 gates.json.subject_hash 匹配，失配 block executing-plans / codex-review skill
- commit_guards 联动检查 doc_sync_guard / logging_guard / refactor_guard / module_governance_guard
- scope_guard T3 commit 必须在 plan Task 声明文件范围内
- 每批 commit 前 `git diff --cached --name-only` 必查（L-KG-3a-2 教训）
- Windows bash 下路径用 forward slash，Vitest 路径过长注意引号包裹
- 前端测试路径**真实目录**是 `frontend/src/__tests__/knowledge-tree/`（plan R6 已校正，注意不要误用旧路径 `frontend/src/components/knowledge-tree/__tests__/`）

---

# 启动 Prompt（复制到新 Planner 会话）

```
[edu-cloud] Planner | 2026-04-14 12:15:00
项目目录: C:\Users\Administrator\edu-cloud
Tier: T3（kg-phase1 Phase 1 Batch 3.b/3.c 验收 + 推进）

读取 C:\Users\Administrator\edu-cloud\docs\plans\2026-04-13-knowledge-graph-phase1-planner-handoff.md（本文件）
参考 C:\Users\Administrator\edu-cloud\docs\plans\2026-04-13-knowledge-graph-phase1-state.json（任务状态）
参考 C:\Users\Administrator\edu-cloud\docs\plans\2026-04-13-knowledge-graph-phase1-gates.json（Gate 回执）
参考 C:\Users\Administrator\edu-cloud\docs\plans\2026-04-13-knowledge-graph-phase1-plan.md（T11-T14 本体，R6 版，line 2783-3965）

首件事：跑 `git log --oneline f9ab3a1..HEAD` + `ls docs/plans/2026-04-13-knowledge-graph-phase1-review-handoff-batch3b.md 2>&1` + `ls docs/plans/2026-04-13-knowledge-graph-phase1-review-report-batch3b*.md 2>&1`，按 planner-handoff §Step 1 的四种情形判定当前位置。

Planner 职责：规划 + 验收，不执行代码。Batch 3.b Gate 2 PASS 后推 3.c；3.c PASS 后 Phase 1 收尾（design.md [实现完成] + edu-cloud/CLAUDE.md 参考文档段新增条目 + 全局 CLAUDE.md 进行中→已完成 迁移 + 最近 sync 落盘记录追加）。

核心教训（planner-handoff §上轮 Planner 会话核心教训）：L-KG-3a-1 独立核查代码 / L-KG-3a-2 staging 污染检查 / L-KG-3a-3 Gate 1 再审触发 / L-KG-3a-4 Tier 立即声明。

关键约束：
- 禁自行 Edit 代码（只改 plan/state/handoff/CLAUDE.md 等规划文件）
- 每次决策要 grep/read 真实代码核查，不盲信 Executor 单方 scope 分析
- commit 前 git diff --cached --name-only 确认 staging 纯净
- Tier 须立即声明 T3（若 session_guard block 用 SessionState 脚本补写）

测试基线（planner-handoff §测试基线）：前端 24 files/233 tests、后端 knowledge_tree 160、stats_service 13。
```
