<!-- no-projectctl -->
---
type: handoff
created: 2026-04-26 23:02:12
project_dir: /home/ops/projects/edu-cloud
design: /home/ops/projects/edu-cloud/docs/plans/2026-04-26-systematic-dev-plan-design.md
plan: /home/ops/projects/edu-cloud/docs/plans/2026-04-26-sprint1-revised-plan.md
---

# edu 系统性开发 — Sprint 1 执行交接卡

=== 生成块开始 ===
**task_id**: sprint1-revised
**topic**: edu-systematic-dev
**project_dir**: /home/ops/projects/edu-cloud
**effective_tier**: T2
**gate_status**: sprint0 完成（GPT review PASS after revert 0efe1e8），sprint1 plan committed 787f229
**last_verified_evidence**: vitest 373/0 + pytest 2199/21(既有债) + vite build OK @ master 787f229
**subject_hash**: N/A
**raw_output_hashes**: N/A
**timestamp**: 2026-04-26T23:02:12+08:00
=== 生成块结束 ===

=== 自由备注开始 ===
- Tier: T2（Sprint 1 修正版 4 Task，无跨模块重构）
- Plan: `/home/ops/projects/edu-cloud/docs/plans/2026-04-26-sprint1-revised-plan.md`
- 调研结论：ErrorBookPage(316行)/QuestionBankPage(345行)/DashboardPage(596行) 全已存在，scope 缩为加固
- T1 Alembic 多 head 最优先（`alembic heads` 返回多 revision，6 migration 测试 FAIL）
- T4 Sprint 2 调研需验证 homework/academic/calendar 前端页面是否也已存在（防重复 Sprint 1 的错误）
- GPT 审查回退了 Agent 错误测试修复（878d1a7→0efe1e8），当前测试全绿不要再改
- 纪律：调研清楚再动手 + Agent prompt 注入全局上下文（详见 design.md 纪律 1/2）
- 使用 codex-review skill 对 Sprint 1 完成后做 GPT 独立审查
=== 自由备注结束 ===
