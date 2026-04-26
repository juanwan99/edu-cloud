---
type: handoff
created: 2026-04-23 20:30:00
project_dir: /home/ops/projects/edu-cloud
---

# grading-prompt-migration Handoff

=== 生成块开始 ===
**task_id**: grading-prompt-migration-2026-04-23
**topic**: 2026-04-23-grading-prompt-migration
**project_dir**: /home/ops/projects/edu-cloud
**effective_tier**: T3
**gate_status**: plan written, pending codex-review
**last_verified_evidence**: zhixue-server cloned at ~/projects/zhixue-server-git; edu-cloud 238 vitest + 1963 pytest pass
**subject_hash**: N/A
**raw_output_hashes**: N/A
**timestamp**: 2026-04-23T20:30:00+08:00
=== 生成块结束 ===

=== 自由备注开始 ===
- T3 迁移任务：将 zhixue-server 的 AI 阅卷 prompt 体系迁移到 edu-cloud
- Plan 在 `docs/superpowers/plans/2026-04-23-grading-prompt-migration.md`
- Phase 1 共 8 个 Task，用 subagent-driven-development 执行
- zhixue 源码参考：`~/projects/zhixue-server-git/src/config/prompts/` + `src/services/llmService.js`
- 关键改动：prompts.py 拆为 prompts/ 包 + 新增 json_parser + rubric_formatter + llm_client 扩展 + worker 两步管线
- 当前分支 feat/conduct-roadmap-batch1 有未提交改动（DocCropPanel/AiGradingPage 等），建议先提交或新建分支
- edu-cloud 后端测试基线：1963 passed / 23 skipped
- edu-cloud 前端测试基线：238 vitest passed
=== 自由备注结束 ===
