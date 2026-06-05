<!-- no-projectctl -->
---
type: handoff
created: 2026-06-05 10:40:00
project_dir: /home/ops/projects/edu-cloud
design: N/A（设计内联总纲 §4 前置 + 引用 83d04fd spec）
plan: /home/ops/projects/edu-cloud/docs/plans/2026-06-05-foundation-governance-master-plan.md
---

# Foundation Governance Master Plan Handoff

=== 生成块开始 ===
**task_id**: N/A
**topic**: foundation-governance-master-plan
**project_dir**: /home/ops/projects/edu-cloud
**effective_tier**: T3
**gate_status**: 无 PASS gate（engine plan-review R5=FINDINGS，定稿于 R5 处置态）
**last_verified_evidence**: engine_plan_review R5 verdict=FINDINGS @ 2026-06-05_103336（.review-receipts.jsonl）
**subject_hash**: N/A
**raw_output_hashes**: N/A
**timestamp**: 2026-06-05 10:40:00
=== 生成块结束 ===

=== 自由备注开始 ===
- Tier: T3。降级：projectctl 未部署 → no-projectctl 模式，hash 为 N/A。
- Goal: 总纲（地基治理 + StudentAnswer 收敛）定稿于 R5 处置态；下一步 Phase -1 收口未提交 governance 工作 → 各 Phase 各自 plan-review。核心：跨科目/归属链写入漏洞机制化杜绝（零裸写守卫）。
- Must Preserve: §3.1 C1–C5 可执行契约 + Phase 4 前置内联设计（批量入口完整归属链 = R3 修的真实安全缺口）；收敛轨迹 R1=4→R2=4→R3=3→R4=2→R5=4。
- Must Not Change: 不写 plan_review PASS（R5=FINDINGS 不捏造）；不碰工作区 ~50 个未提交 governance 代码（非本线所写，Phase -1 先收口）；WONTFIX 不重开（F-002 update/delete 越界、F-003 同名 design 冗余）。
- 启动 prompt（新会话粘贴）: 读 `/home/ops/projects/edu-cloud/docs/plans/2026-06-05-foundation-governance-master-plan.md`，从 Phase -1 收口未提交 governance 工作；每批代码改动用 codex-review skill 审查。
=== 自由备注结束 ===
