# Active Document Index

Use this index before reading historical `docs/plans/**`. Anything not listed here is historical or candidate context, not active truth.

## Active

| Path | Status | Use |
|---|---|---|
| `AGENTS.md` | active | Codex entrypoint and hard rules |
| `docs/context/GOVERNANCE_MODEL.md` | active | 元守双核心 model |
| `docs/context/META_RUNTIME.md` | active | Meta Core task-contract runtime |
| `docs/context/GUARDIAN_RUNTIME.md` | active | Guardian Core realtime runtime contract |
| `docs/context/NOW.md` | active | Current facts and risks |
| `docs/context/COMMANDS.md` | active | Command reference |
| `docs/context/LESSONS.md` | active | Project-specific migrated lessons |
| `docs/context/CLAUDE_AUX.md` | active | Claude Code read-only auxiliary model protocol |
| `docs/context/SAFETY_MATRIX.md` | active | Rule enforcement map |
| `docs/context/ARTIFACT_POLICY.md` | active | Local artifact, backup, screenshot, and scratch-script policy |
| `.github/workflows/test.yml` | active | CI smoke checks for the Codex governance layer plus existing backend/frontend jobs |

## Candidate Active Work

| Path | Status | Notes |
|---|---|---|
| `docs/essay-scoring-handoff.md` | candidate-active | AI作文评分/锚点/盲测 facts are current and match dirty AI grading area. |
| `docs/2026-05-02-grading-pipeline-optimization-handoff.md` | candidate-active | Earlier AI grading pipeline context; likely partly superseded by essay-scoring handoff. |
| `docs/plans/2026-05-05-grading-progress-split-plan.md` | candidate-active | Recent grading progress plan; verify implementation state before using. |
| `docs/plans/2026-05-05-logging-system-redesign.md` | candidate-active | Logging redesign design; not part of Codex migration P0. |
| `docs/plans/2026-05-06-choice-scan-handoff.md` | candidate-active | User-provided handoff for Jingyan biology/geography choice-scan recovery; not part of the current Dual-Core governance task. Verify DB/template state before execution. |
| `docs/scan-calibration-handoff.md` | candidate-active | 2026-05-17 OMR calibration results and current `calibrate_scan.py` / `calibrate_universal.py` commands; verify DB and scan files before execution. |
| `scripts/governance/check_module_semantics.py` + `docs/governance/module-semantics.yaml` + `frontend/src/router/index.js` | candidate-active | Phase 0.5 static guard + 0.6 runtime authGuard gating (main body `f51342a`/`8606ac6`/`bf421e8`/`bd8be46`) + **0.6C coverage-completeness implemented** (`70eeac2`/`b1a6d09`/`61ed166`): router_meta 升完整门控面、profile 前后端门控补齐、F-001/F-002 收口。Guard clean + tests green. R5 复审确认 R4 三 finding FIXED（0.6C 达标）；R5 新报 2 个 scope 外 design_concern 转 Phase 0.7。See NOW.md "Module Governance". **No Portal/Phase 1 until Phase 0.7 R5-DC1 处置或明确解锁。** |
| `docs/plans/2026-06-06-phase06-coverage-handoff.md` | candidate-active | Phase 0.6C coverage-completeness sub-task handoff (**done**, R4 findings FIXED & R5-confirmed). Root-cause fix for R4 F-002 (guard enforces moduleCode on every controlled route) + F-001 (`/profile/student/:studentId` direct-URL fail-open). Goal/Must Preserve/Must Not Change inside. |
| `docs/plans/2026-06-06-phase07-drift-burndown.md` | candidate-active | Phase 0.7 模块门控 drift burn-down（R5 carve-out）。2 scope 外 design_concern（菜单层 fail-open MED + 守卫/中间件匹配漂移 LOW）+ 现存 known_drift 清单。**Portal Phase 1 BLOCKED until R5-DC1 处置或明确解锁。** |

## Completed / Reference

| Path | Status | Notes |
|---|---|---|
| `docs/sidebar-modular-restore-handoff.md` | completed-reference | Header says Part A/B completed and Part C hook work implemented. |
| `docs/marking-assign-handoff.md` | completed-reference | Header says assignment redesign implemented. |
| `docs/plans/2026-04-29-truthline-p0-handoff.md` | reference | Truthline context only; current command is `scripts/truth`. |
| `docs/plans/2026-04-29-truthline-p0-review-report.md` | reference | Review evidence only. |
| `docs/plans/2026-05-12-agent-optimization-design-v2.md` | reference | Pydantic AI engine design referenced by `2026-05-12-agent-pydantic-ai-handoff.md`; current code imports pydantic_ai. |
| `docs/superpowers/plans/2026-05-24-role-workbench-optimization.md` | reference | Role-specific workbench optimization planning record. |
| `docs/superpowers/plans/2026-05-24-formal-role-workbench-rollout.md` | reference | Formal rollout plan for active-role dashboard/sidebar behavior. |

## Historical

- `docs/plans/archived/**`
- Pre-takeover plans marked `<!-- pre-takeover: archived for history, not active spec -->`
- Windows-era handoff numbers, paths, and timelines
- Old review logs not explicitly listed above

## Rule

When a task cites an old plan or handoff, first add it here with status `candidate-active` or `reference`, including why it is safe to read.
