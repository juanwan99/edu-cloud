---
type: handoff
created: 2026-04-22 07:04:00
project_dir: /home/ops/projects/edu-cloud
design: N/A
plan: N/A
---

# grading-dispatch-integration Handoff

=== 生成块开始 ===
**task_id**: grading-dispatch-integration-2026-04-22
**topic**: exam-flow-scan-grading-integration
**project_dir**: /home/ops/projects/edu-cloud
**effective_tier**: T2
**gate_status**: N/A
**last_verified_evidence**: build 234/234 vitest pass; auto-detect-cv opencv-only 0.4s/6regions; dispatch/status 8 subjects; Playwright screenshot 8 cards
**subject_hash**: N/A
**raw_output_hashes**: N/A
**timestamp**: 2026-04-22T07:04:00+08:00
=== 生成块结束 ===

=== 自由备注开始 ===
- 8 文件 +642/-300 行未 commit（布局重构+OpenCV 集成+跨校权限修复）
- 详细接手指南见 `2026-04-22-grading-dispatch-integration-startup-prompt.md`
- **下一步**：验证切割全链路 → commit → StudentsPage 排查
- 考试：二中枫溪 `1cf6a4b8-...`，9 科 4364 张已上传，dispatch 返回 8 科（缺历史待查）
- 登录 superadmin/123456 切到二中枫溪角色操作
=== 自由备注结束 ===
