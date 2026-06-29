<!-- no-projectctl -->

=== 生成块开始 ===
task_id: T2-choice-scan-grading
topic: choice-scan-grading
project_dir: ~/projects/edu-cloud
effective_tier: T2
gate_status: N/A
last_verified_evidence: Question 50 条已入库; 错误 answers 68100 条已清理; scans 在 uploads/scan-input/
subject_hash: ba8132b
raw_output_hashes: N/A
timestamp: 2026-05-06 21:30:00
=== 生成块结束 ===

=== 自由备注开始 ===
阻塞项: 模板 choice_group 布局错误（定义 25row×4col，实物是 5row×5col 多列布局）。
修复: 拆为 5 个 choice_group 区域，精确标定坐标后重跑识别。
详见启动 prompt: docs/plans/2026-05-06-choice-scan-startup-prompt.md
Must Preserve: 语文选择题 14751 条 + 全部主观题数据
Must Not Change: students 表、语文科目数据
=== 自由备注结束 ===
