<!-- no-projectctl -->
=== 生成块开始 ===
task_id: T3-phase06-coverage
topic: phase06-coverage-completeness
project_dir: ~/projects/edu-cloud
effective_tier: T3
gate_status: plan_review=pending code_review=pending
last_verified_evidence: codex-review f82df2a..HEAD = R4 FINDINGS(3); tests/governance 166 pass; router.test.js 41 pass; vitest 2483 pass/3 pre-existing
subject_hash: bd8be46
raw_output_hashes: N/A
timestamp: 2026-06-06 16:20:00
created: 2026-06-06 16:20:00
=== 生成块结束 ===
=== 自由备注开始 ===
# Phase 0.6 Coverage-Completeness

**Goal**: 守卫层强制「每个受控 route（`fr` 非 null）在 authGuard 可消费真源标 moduleCode」→ guard-green == 运行时无 fail-open。根治 R4 F-002（`GATING_SURFACES` 与 authGuard 门控面脱节）。

**首要安全项 F-001 HIGH**: `/profile/student/:studentId` 有 `view_scores` 无 moduleCode，`study_analytics` 关闭时直达 fail-open（后端 `/api/v1/profile` 亦 pass-through）。优先堵。

**设计种子**: ①守卫加「消费面覆盖」检查取代 router_meta 文档面豁免 ②补全缺码 route（profile + calendar/error-book/homework/knowledge-tree/question-bank）③authGuard 真源统一 ④改 R2-A4 等豁免测试。

**Must Preserve**: admin 无校豁免 / 有校 fail-closed / loadModules 失败给空 / 9 module-gating + drift 测试 / 主体 4 commit（`f51342a`/`8606ac6`/`bf421e8`/`bd8be46`）不回退。
**Must Not Change**: 不进 Portal（PASS 前）/ 不回退 A/B/R3 / 改 meta 前查依赖。

详情见 `docs/context/NOW.md`「Module Governance Phase 0.5 + 0.6」。
=== 自由备注结束 ===
