---
type: handoff
created: 2026-04-29 20:42:18
project_dir: /home/ops/projects/edu-cloud
design: /home/ops/docs/truthline-design-consensus.md
plan: /home/ops/projects/edu-cloud/docs/superpowers/plans/2026-04-29-truthline-p0.md
---

# Truthline P0 Handoff

=== 生成块开始 ===
**task_id**: truthline-p0
**topic**: truthline-p0
**project_dir**: /home/ops/projects/edu-cloud
**effective_tier**: T3
**gate_status**: plan_written, pending_execution
**last_verified_evidence**: plan file hash 35c44e95b0adf049 @ 2026-04-29T20:42
**subject_hash**: 35c44e95b0adf049
**raw_output_hashes**: N/A
**timestamp**: 2026-04-29T20:42:18+08:00
=== 生成块结束 ===

=== 自由备注开始 ===
- Tier: T3
- Goal: 实现 Truthline P0 真相可见化——版本指纹注入 + `truth status` / `truth doctor` CLI，让"AI 改的 vs 用户看到的"断裂可秒级定位
- Must Preserve: `npm run build` 产出可用 dist/（ORC-1）；前端 2404 tests 全绿（ORC-2）；`/api/v1/version` 向后兼容保留 version+boot_time（ORC-5）；dist/ 权限 nginx 可读（ORC-4）
- Must Not Change: nginx 配置；systemd service 文件；现有 hook 体系；前端路由和业务组件；后端业务逻辑
- Plan: `/home/ops/projects/edu-cloud/docs/superpowers/plans/2026-04-29-truthline-p0.md`
- Design: `/home/ops/docs/truthline-design-consensus.md`
- 启动 prompt: `读取 /home/ops/projects/edu-cloud/docs/superpowers/plans/2026-04-29-truthline-p0.md，使用 superpowers:executing-plans skill 按 Task 1-7 逐步执行。完成后使用 codex-review skill 做代码审查。`
=== 自由备注结束 ===
