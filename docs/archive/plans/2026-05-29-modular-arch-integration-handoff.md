<!-- no-projectctl -->
=== 生成块开始 ===
task_id: T3-modular-arch-integration
topic: modular-arch-integration
project_dir: ~/projects/edu-cloud
effective_tier: T3
gate_status: plan_review=fail code_review=pending
last_verified_evidence: codex-review plan FAIL (6 HIGH+1 MED 全部工具验证属实); 修复后 40 passed (test_base_service+test_event_bus)
subject_hash: a65c480
raw_output_hashes: N/A
timestamp: 2026-05-29 12:18:05
created: 2026-05-29 12:18:05
=== 生成块结束 ===
=== 自由备注开始 ===
# 模块化新架构「接入」设计议题（承接 P0-P6；plan FAIL；已定：搁置接入、先清隐患）

**Goal**: 决定新架构（模块自注册/SecureRouter/权限编译器/事件总线/BaseService）是否接入生产；接入须同步解决暴露的安全/事务/边界问题。走 brainstorming→design，勿直接改代码。

**Must Preserve（接入前唯一生产路径，不可破坏）**: `app.py:351 register_all` 旧路由表；`auth.py` 旧 Permission/ROLE_PERMISSIONS 鉴权；旧 `event_bus`(.on/.emit)。

**Must Not Change（未设计前红线）**: 未定 fail-closed 前禁止模块继承 `BaseService`（F-005 租户漏洞）；勿把权限编译器直接接 auth（F-003）；勿依赖 `buffer/flush_events`（F-004 空壳）。

**待设计议题**: F-001/F-003 接入·F-005 租户 fail-closed·F-004 事件事务·F-002 边界 139 违规建 baseline。详见 `docs/plans/2026-05-29-modular-arch-diagnosis.md` 处置矩阵（+ 原 plan + `.codex-plan-review-raw.log`）。
=== 自由备注结束 ===
