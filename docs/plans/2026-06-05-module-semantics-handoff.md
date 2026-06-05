<!-- no-projectctl -->
---
type: handoff
created: 2026-06-05 21:30:00
project_dir: /home/ops/projects/edu-cloud
design: /home/ops/projects/edu-cloud/docs/superpowers/specs/2026-06-05-module-semantics-design.md
plan: /home/ops/projects/edu-cloud/docs/superpowers/plans/2026-06-05-module-semantics-implementation.md
---

# Phase 0.5 模块语义统一 Handoff

=== 生成块开始 ===
**task_id**: phase05-module-semantics
**topic**: module-semantics
**project_dir**: /home/ops/projects/edu-cloud
**effective_tier**: T3
**gate_status**: plan-review FINDINGS（R1=4 → R2=3 → R3=4 不收敛，本 topic 无 PASS gate）
**last_verified_evidence**: commit d531ce5（R2 处置，工作区 clean；三个待建文件未创建，无代码实现）
**subject_hash**: N/A
**raw_output_hashes**: N/A
**timestamp**: 2026-06-05 21:30:00
=== 生成块结束 ===

=== 自由备注开始 ===
- Tier T3。HEAD=d531ce5；module-semantics.yaml / check_module_semantics.py / test_module_semantics.py 三件未创建，尚未进任何实现。
- 根因(勿再犯)：①事实基线照搬非实测(subjects 错；实测顶层仅 36 个 /api/v1/<seg>，subjects 实为 /exams/{id}/subjects 嵌套) ②逐条打补丁引入新局部不一致。
- 待用户拍板方向：A=真源由 app.routes 实测生成 / B=plan+spec 全量对齐口径 / C=拆 topic；上窗口倾向 A+B。接手先问方向，别闷头改。
- 必修6项：①删 /api/v1/subjects，计数 37→36 ②CI 改走 pytest+装项目依赖(governance job 无 .venv 且守卫需 import create_app，原方案会失败) ③补 dashboard action 的 route 级比对 ④spec stale 计数同步(8 处→11、十条→十六) ⑤File Structure 段 5→6 个 check ⑥risk_modules 补 schoolSettings.js。
- Must Preserve：逐入口真源 + app.routes 展开 + 四元组 drift + frontend 探测(_FRONTEND_DRIFT_PROBES) + 4 fail-open(academic/conduct/exam-imports/profile)定性。
- Must Not Change：行为不变(消费者源码零改)；不修 fail-open/studio/teaching；不动 AI 工具 module_code；不进 Portal 功能/Phase1 前端迁移。
- 启动 prompt：确认 HEAD=d531ce5 → 问用户方向 A/B/C → 修6项并全量对齐 → 用 codex-review skill 重跑 plan-review 拿本 topic PASS gate → 才进 YAML→守卫→测试→CI 实施。
=== 自由备注结束 ===
