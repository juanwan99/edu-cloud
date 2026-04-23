---
type: handoff
created: 2026-04-21 11:59:00
project_dir: /home/ops/projects/edu-cloud
design: N/A
plan: N/A
---

# exam-flow-and-teacher-mgmt Handoff

=== 生成块开始 ===
**task_id**: exam-flow-2026-04-21
**topic**: exam-flow-and-teacher-mgmt
**project_dir**: /home/ops/projects/edu-cloud
**effective_tier**: T2
**gate_status**: N/A
**last_verified_evidence**: playwright screenshot 6/6 pass; AI grading 1 answer scored (score=2.0 confidence=0.9); teacher export 238 rows 15 cols verified
**subject_hash**: N/A
**raw_output_hashes**: N/A
**timestamp**: 2026-04-21T11:59:00+08:00
=== 生成块结束 ===

=== 自由备注开始 ===
- Tier: T2 即兴执行（无 plan/design，直接排障+实现）
- 15 文件改 + 6 新文件全在 working tree **未 commit**，需拆 commit
- AI 阅卷链路已通：.env LLM_SLOT=grading-vision + /v1 路径 + worker ORM import 修复 + prompt 防截断
- 化学 4 题 Rubric 已建；其余科目 47 道主观题 Rubric 待补
- 教师 User 表已 ALTER TABLE 加 9 列；teacher_router 导入导出含 15 列 + 学科班级
- nginx: edu.momowan.xyz 已删，唯一入口 https://mcu.asia（mcu-asia.conf）
- build 脚本追加 chmod + www-data 入 ops 组，403 永久修复
- Worker 启动: `.venv/bin/python /tmp/start_worker.py`（arq CLI 与 Python 3.14 不兼容）
- 下一步: commit → build 部署 → 补 Rubric → 手动打分验证 → 成绩发布
- 月考 exam_id: `80f4fc02-bc73-40f5-9fb7-83de5b9bbd9c`; 教务登录: `admin_academic_director_2/123456`
=== 自由备注结束 ===
