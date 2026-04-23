---
type: handoff
created: 2026-04-23 14:00:00
project_dir: /home/ops/projects/edu-cloud
---

# navigation-back-button Handoff

=== 生成块开始 ===
**task_id**: navigation-back-button-2026-04-23
**topic**: 2026-04-23-navigation-back-button
**project_dir**: /home/ops/projects/edu-cloud
**effective_tier**: T2
**gate_status**: N/A
**last_verified_evidence**: frontend 238 vitest pass
**subject_hash**: N/A
**raw_output_hashes**: N/A
**timestamp**: 2026-04-23T14:00:00+08:00
=== 生成块结束 ===

=== 自由备注开始 ===
- T2 任务：前端子页面缺返回按钮，用户进入后无法回上一级
- 必改 5 个文件：ExamDetail/CardEditorDev/GradingResults/MarkingAssign/MarkingProgress
- 可选 conduct 8 页 + analytics 2 页
- 详细调查和实现规范见 startup-prompt.md
- 统一用明确路径 router.push，不用 router.back()
- ExamDetailPage 980 行大文件，只加返回按钮不碰其他
- 验证：vitest run + vite build + 浏览器点击验证
=== 自由备注结束 ===
