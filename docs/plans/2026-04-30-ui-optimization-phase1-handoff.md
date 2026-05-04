<!-- no-projectctl -->
=== 生成块开始 ===
task_id: T3-ui-optimization-phase1
topic: ui-optimization
project_dir: ~/projects/edu-cloud
effective_tier: T3
gate_status: {plan_review: pass, code_review: pending}
last_verified_evidence: grep -E baseline=666 硬编码颜色，与 plan baseline_count 一致
subject_hash: 49f38e4
raw_output_hashes: N/A
timestamp: 2026-04-30 23:08:59
created: 2026-04-30 23:08:59
=== 生成块结束 ===
=== 自由备注开始 ===
Phase 1：3 个 commit 建立 Token 体系（variables.css + theme.js + global.css）。
只加不删，禁止改页面/组件文件。旧变量 51 个全保留，新 Token 用 --r-*/--fs-*/--fw-*/--lh-*/--text-* 不冲突命名追加。
详细执行指令见 docs/plans/ui-optimization-phase1-startup-prompt.md。
完整计划见 docs/plans/2026-04-30-ui-system-optimization-plan.md（GPT R4 PASS）。
核心铁律：如果发现自己在删变量或改组件文件——超出 scope，立即停下。
=== 自由备注结束 ===
