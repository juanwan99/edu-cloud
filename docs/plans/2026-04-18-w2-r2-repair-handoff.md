<!-- legacy-format -->
# W2-R2 · kg Phase 1 Batch 3.b · Code Review R1 FAIL 修复 · 执行交接卡

> 类型：Code Review R2 修复窗口（W2 Gate 2 R1 FAIL → R2 修复）
> 创建：2026-04-18 规划窗口（基于实查 commit 931e1c7 + R1 报告）
> 工作分支：`feat/kg-batch3b` @ `931e1c7`
> 工作 worktree：**`/home/ops/projects/edu-cloud-w2`**（已独立检出）
> 前置 R1 报告：`docs/plans/2026-04-13-knowledge-graph-phase1-review-report-batch3b.md`（GPT 5.4，5 findings）

## 1. R1 FAIL 5 findings 摘要（依据：R1 report 实查）

| # | 严重 | 类型 | 标题 | 修复方向 |
|---|------|------|------|---------|
| **F001** | （未列严重，HIGH 级） | code-bug | ExamItemsTab `load()` 无 seq guard / AbortController | 沿用同目录 `NodeDetailDrawer.vue:140-183` 已有 `fetchSeq` 序号守卫 pattern |
| **F002** | HIGH | test-gap | ExamItemsTab "pagination triggers reload" 测试不触发翻页 | 改测试断言 prevPage/nextPage 调用 + watch 重置 page；mutant test：删除 prevPage/nextPage 必须红 |
| **F003** | MED | test-gap | TreeNavPanel 用 `wrapper.vm.navMode = 'chapter'` 直接操作组件实例，偏离 plan §3185 "模拟点击 radio button" | 改用 DOM 层 `wrapper.find('input[type=radio]').trigger('change')` 触发 |
| **F004** | MED | test-gap | StudyUnitTab fixture 无 0 值，`?? '—'` vs `\|\| '—'` 测不出差异 | fixture 加 0 值 case；mutant test：`?? '—'` → `\|\| '—'` 必须红 |
| **F005** | freshness | process | `defineExpose({ navMode, handleSelect })` 引入未列 public API（plan §3181 明文 navMode 不暴露外部） | 移除 defineExpose；测试改 DOM 入口；或更新 plan §3181 列入 contract（需用户决策） |

## 2. 修复决策点（必须先与用户确认）

**F005 决策**（Q1）：
- A) 移除 `defineExpose`，测试全改 DOM 入口（保持 plan 契约不变）
- B) 更新 plan §3181 加 navMode 进 public API（contract 变更需用户批准 behavior_change）

**推荐 A**（不改 contract 最小风险），但 R2 executor 必须先报告等用户拍板。

## 3. 范围定义

### 3.1 可改文件（白名单）
- `frontend/src/components/knowledge-tree/ExamItemsTab.vue`（F001 加 fetchSeq guard）
- `frontend/src/__tests__/knowledge-tree/ExamItemsTab.test.js`（F002 改测试断言）
- `frontend/src/__tests__/knowledge-tree/TreeNavPanel.test.js`（F003 改 DOM 入口）
- `frontend/src/__tests__/knowledge-tree/StudyUnitTab.test.js`（F004 加 0 值 fixture）
- `frontend/src/components/knowledge-tree/TreeNavPanel.vue`（F005 选 A 移 defineExpose）

### 3.2 红线禁区
- 不动后端 `src/edu_cloud/modules/knowledge_tree/*`
- 不动 `frontend-nuxt/*` （W3 范围）
- 不动 `src/edu_cloud/modules/card/*` （W1 范围）
- 不动 `src/edu_cloud/modules/conduct/*` （W4 范围）
- 不动 W2 已 commit 的非 finding 关联文件（如 NodeDetailDrawer.vue 主 tab 结构、useKnowledgeTree.js）

## 4. 实施步骤

```bash
cd /home/ops/projects/edu-cloud-w2

# Step 0: verify 起点
git log --oneline -3  # 应见 931e1c7 / 26f2af5 / 5607a9a
git status            # working tree 应仅有 review log + node_modules

# Step 1-5: 逐 finding 修复（每个 finding 独立 commit）
# Step 1: F001 ExamItemsTab fetchSeq guard
# Step 2: F002 ExamItemsTab.test.js mutant 断言
# Step 3: F003 TreeNavPanel.test.js DOM 入口
# Step 4: F004 StudyUnitTab.test.js 0 值 fixture
# Step 5: F005 移 defineExpose（如选 A）+ TreeNavPanel.test.js 改 DOM 入口

# Step 6: 测试子集 verify
cd frontend && npx vitest run src/__tests__/knowledge-tree/ 2>&1 | tail -5
# 预期：≥9 + ≥3 + ≥2 = 原 153 + 新增 mutant test 全 PASS
# Mutant verify：手动注释掉 fetchSeq / prevPage / 0-handling，对应测试必须红

# Step 7: 触发 codex-review R2
export AIPROXY_OAI_KEY="$(cat ~/.secrets/aiproxy.key)"  # 用 W4 已 verify 的 key 路径
# 调 codex-review code_review_batch3b round=2
```

## 5. 验收契约
- 5 finding 全部 resolved（R2 报告标 resolved-correct）
- mutant verify 通过（删除目标实现，对应测试必须红）
- vitest 子集 100% PASS（不破坏现有 153）
- 不动红线文件
- F005 决策路径清晰记录到 commit message 或 R2 修复说明

## 6. checkpoint 输出格式

```
【W2-R2 修复 · 待汇总】
- 工作分支：feat/kg-batch3b
- R2 commits（按 finding）：F001 <sha> / F002 <sha> / ... / F005 <sha>
- vitest：N passed / 0 failed（含 mutant 增量）
- F005 决策：A 移 defineExpose / B 改 plan
- codex-review R2 task ID：<id>，结果：PASS/FAIL（PASS 才进 T2 partial-W2）
- 异常：<列出>
- 等 T2 汇总（W2 partial-merge）
```

## 7. 与其他窗口同步
- 零文件冲突（W1/W3/W4 红线均互斥）
- 不直接 commit master
- W2 R2 PASS 后由 T2-补遗 session merge 到 master

## 8. 第一步指令

```bash
cd /home/ops/projects/edu-cloud-w2
cat /home/ops/projects/edu-cloud-w2/docs/plans/2026-04-13-knowledge-graph-phase1-review-report-batch3b.md  # 必读 R1 5 findings 全文
cat /home/ops/projects/edu-cloud-t2/docs/plans/2026-04-18-w2-r2-repair-handoff.md  # 必读本卡
git log --oneline -5
git status
# 报告："已读 R1 5 findings + 本卡，F005 决策请用户拍板 A/B 后开 Step 1"
```

## 9. 兜底
- F001 fetchSeq pattern 不熟 → 读 NodeDetailDrawer.vue:140-183 复用
- mutant test 写不出 → 输出"超出能力边界" + 调用 Codex 协助
- 同 finding 修 ≥3 次仍 R3 FAIL → L015 主动放弃
