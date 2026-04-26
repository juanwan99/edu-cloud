---
type: handoff
created: 2026-04-23 15:30:00
project_dir: /home/ops/projects/edu-cloud
---

# ai-grading-entry Handoff

=== 生成块开始 ===
**task_id**: ai-grading-entry-2026-04-23
**topic**: 2026-04-23-ai-grading-entry
**project_dir**: /home/ops/projects/edu-cloud
**effective_tier**: T2
**gate_status**: N/A
**last_verified_evidence**: frontend 238 vitest pass; AiGradingPage 已存在
**subject_hash**: N/A
**raw_output_hashes**: N/A
**timestamp**: 2026-04-23T15:30:00+08:00
=== 生成块结束 ===

=== 自由备注开始 ===
- 侧边栏"AI 阅卷"错指向扫描调度页，用户看到切割进度而非 AI 阅卷
- 修复：AiGradingPage 加考试/科目选择器，新增 /ai-grading 无参路由
- 侧边栏改指 /ai-grading，GradingDispatchPage 标题改回"扫描调度"
- 改 4 文件：AiGradingPage + router + sidebarConfig + GradingDispatchPage
- 详细方案见 startup-prompt.md
- 同时执行 navigation-back-button handoff（5 个子页面加返回按钮）
=== 自由备注结束 ===
