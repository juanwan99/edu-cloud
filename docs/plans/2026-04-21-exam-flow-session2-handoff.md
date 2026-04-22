---
type: handoff
created: 2026-04-21 19:10:00
project_dir: /home/ops/projects/edu-cloud
design: N/A
plan: N/A
---

# exam-flow-session2 Handoff

=== 生成块开始 ===
**task_id**: exam-flow-session2-2026-04-21
**topic**: exam-flow-and-teacher-mgmt
**project_dir**: /home/ops/projects/edu-cloud
**effective_tier**: T2
**gate_status**: N/A
**last_verified_evidence**: build pass; export 23 rows with 班主任(2302) labels; AI grading 40 results; publish → 2183 snapshots
**subject_hash**: N/A
**raw_output_hashes**: N/A
**timestamp**: 2026-04-21T19:10:00+08:00
=== 生成块结束 ===

=== 自由备注开始 ===
- 考试流程端到端已通：Rubric 47 条 / AI 阅卷 / 手动打分 / 成绩发布全通过
- 教师管理 9 次 fix（2f78303→f2aeff7）：角色分离（subject_teacher+homeroom_teacher）、学校选择器、导出花名册/模板/网页三者格式一致
- 二中枫溪 22 教师 30 条 UserRole 已建，superadmin 切"教务主任(二中枫溪)"查看
- 分支 feat/conduct-roadmap-batch1，ahead origin 10 commits，未 push
- **下一步**：浏览器验证教师页 → StudentsPage 同类排查（L019 警示勿逐症状修）→ OFD 转 Word（文件待上传）
- 数学大题 max_score=0 未修（Rubric 默认 12 分），语文第 23 题 180 分待确认
- Worker：`.venv/bin/python /tmp/start_worker.py`；教务登录：育才 `admin_academic_director_2/123456`
=== 自由备注结束 ===
