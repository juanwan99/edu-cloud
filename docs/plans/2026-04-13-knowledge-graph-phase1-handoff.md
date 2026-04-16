---
type: handoff
created: 2026-04-13 08:25:00
project_dir: C:\Users\Administrator\edu-cloud
design: C:\Users\Administrator\edu-cloud\docs\plans\2026-04-12-knowledge-graph-optimization-design.md
plan: C:\Users\Administrator\edu-cloud\docs\plans\2026-04-13-knowledge-graph-phase1-plan.md
review: C:\Users\Administrator\edu-cloud\docs\plans\2026-04-13-knowledge-graph-phase1-plan-review.md
gates: C:\Users\Administrator\edu-cloud\docs\plans\2026-04-13-knowledge-graph-phase1-gates.json
state: C:\Users\Administrator\edu-cloud\docs\plans\2026-04-13-knowledge-graph-phase1-state.json
---

# 约束与偏好（plan/design 未记录的增量）

- **Tier**: T3 流程。writing-plans 已完成，Gate 1 PASS，**必须在新会话执行**（本会话禁止执行代码）
- **Gate 1 回执**: gates.json 已写入 `plan_review: pass`，经 R1-R5 FAIL → R6 PASS 10 个 finding 全部 resolved。下一个强制 Gate 是 `code_review`（每批次）
- **数据源路径**: knowledge.db 在 `C:\Users\Administrator\edu-knowledge-base\knowledge.db`（非本项目目录），测试时环境变量 `KNOWLEDGE_DB_PATH` 已有默认值
- **MCU-03 路径**: `C:\Users\Administrator\Archive\MCU-03\knowledge_skeleton\`（只读素材，不可修改）
- **Contract Pack 约束**: plan §Contract Pack 定义了 5 个 invariants + 3 反例 + 8 风险模块 + 3 test_debt，Code Review 时必须对照。INV-002（L1-only 图谱）和 INV-004（前端子组件契约不可改）是关键硬约束
- **行为变更规则**: 任何未在 plan Contract Pack 中列出的 public API 变更或 invariant 偏离必须标为 process finding，不可静默引入
- **测试 fixture**: 使用 `db` / `admin_headers` / `client`（conftest.py 已有），不要创建新 fixture 名
- **sync 入口函数**: `sync_knowledge_on_startup`（sync_service.py:188），不要用 `sync_knowledge_tree`
- **前端子组件契约**: TreeNavPanel 的 emits `select-node` 必须传完整 node 对象（不是 id 字符串），这是现有契约（TreeNavPanel.vue:147），修改会破坏 KnowledgeTreePage.vue:19 和 NodeDetailDrawer 的消费
- **ModuleOverviewPanel / TreeNavPanel 原有 props 全保留，只能追加 optional props**（Phase 1 的 F002 教训）
- **NodeDetailDrawer 改造**: 7 tab 纯追加模式（evidence + questions 原标签**不可移除**），这是 F007 behavior_change 的规避方式
- **批次拆分建议**: Plan 有 14 Task (T0 + T1-T13 + T14)，建议 2-3 批：
  - Batch 1: T0-T6（后端 models + 计算服务 + MCU 导入 + sync 集成）
  - Batch 2: T7-T8（API v3 + 新 endpoints）
  - Batch 3: T9-T14（前端 + 收尾）
- **每批完成后输出审查交接单 → codex-review (code) → 下一批**，单批 FAIL 最多 3 轮修复

---

# 启动 Prompt（复制到新会话）

```
[edu-cloud] Executor | 2026-04-13 08:25:00
项目目录: C:\Users\Administrator\edu-cloud

读取 C:\Users\Administrator\edu-cloud\docs\plans\2026-04-13-knowledge-graph-phase1-handoff.md
按 C:\Users\Administrator\edu-cloud\docs\plans\2026-04-13-knowledge-graph-phase1-plan.md 执行 Phase 1。

Gate 1 已 PASS（见 C:\Users\Administrator\edu-cloud\docs\plans\2026-04-13-knowledge-graph-phase1-plan-review.md）。
你只需要按 plan 执行 T0-T14。

使用 executing-plans skill。

建议批次拆分（每批完成后停下做审查）:
- Batch 1: T0-T6 (后端基础)
- Batch 2: T7-T8 (API 扩展)
- Batch 3: T9-T14 (前端 + 收尾)

每批完成后:
1. 更新 state.json 将对应 Task 改为 completed
2. 输出审查交接单（路径 C:\Users\Administrator\edu-cloud\docs\plans\2026-04-13-knowledge-graph-phase1-review-handoff-batch{N}.md）
3. 使用 codex-review skill 进行 GPT 代码审查
4. Code Review PASS 后进入下一批
5. FAIL 时每批最多 3 轮修复

Contract Pack 约束必读（plan §Contract Pack）:
- INV-002: compute_exam_frequency 只返回 L1 concepts，严禁 L0 evidence
- INV-004: TreeNavPanel / ModuleOverviewPanel 现有 props/emits 契约不可改，只能追加 optional
- CE-001/CE-002: 禁止弱断言（wrapper.exists / 200-or-404）

最后一批 PASS 后:
- 更新 C:\Users\Administrator\edu-cloud\docs\plans\2026-04-12-knowledge-graph-optimization-design.md 头部追加 `> [YYYY-MM-DD HH:MM:SS Phase 1 实现完成] Commits: <first>..<last>`
- commit 收尾

完成后输出审查交接单。使用 codex-review skill 进行 GPT 代码审查。
```
