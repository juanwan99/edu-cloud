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
| `scripts/governance/check_module_semantics.py` + `docs/governance/module-semantics.yaml` + `frontend/src/router/index.js` | candidate-active | Phase 0.5 static guard + 0.6 runtime authGuard gating (main body `f51342a`/`8606ac6`/`bf421e8`/`bd8be46`) + **0.6C coverage-completeness implemented** (`70eeac2`/`b1a6d09`/`61ed166`): router_meta 升完整门控面、profile 前后端门控补齐、F-001/F-002 收口。Guard clean + tests green. R5 复审确认 R4 三 finding FIXED（0.6C 达标）；R5 新报 R5 F-001=**MED security_design**（前端 surface fail-open，非可延期 design_concern）+ F-002=LOW design_concern。**Phase 0.7A 已完成**：4 surface 统一门控上下文 fail-closed，对齐 authGuard；复审 R6→R8 收口（R6/R7 RoleSwitcher 动态路由 module/permission 两 MED 已修，R8 零 MED/security）。**Phase 0.7B 已执行**：中间件最长前缀对齐守卫（R5-DC2）+ conduct/exam-imports 补门控 + 5 hygiene 入 exempt + CRLF 收口，known_drift 11→3。**Phase 0.7D 已执行**（`4002d56`/`bfdbd50`）：academic 双面 fail-open 收口——前端三 surface 接 teaching + 后端 /api/v1/academic 补门控，academic-backend-fail-open + teaching-frontend-unwired drift 删除，known_drift 3→1（仅余 studio）；缺 SchoolModule(teaching) 行 pass-through 是全系统既有语义（非 0.7D 引入），设计者 WONTFIX。See NOW.md "Phase 0.7D"。**Portal Phase 1 解锁=设计者决策**（执行工程师不自解锁）。 |
| `docs/plans/2026-06-06-phase06-coverage-handoff.md` | candidate-active | Phase 0.6C coverage-completeness sub-task handoff (**done**, R4 findings FIXED & R5-confirmed). Root-cause fix for R4 F-002 (guard enforces moduleCode on every controlled route) + F-001 (`/profile/student/:studentId` direct-URL fail-open). Goal/Must Preserve/Must Not Change inside. |
| `docs/plans/2026-06-06-phase07-drift-burndown.md` | candidate-active | Phase 0.7 模块门控 drift burn-down（R5 carve-out）。R5-DC1/F-001（MED security_design 前端 surface fail-open）已于 Phase 0.7A 处置。**Phase 0.7B 已执行（`fd89f10`/`0d78f55`/`90c8a93`/`c989e09`）**：① gate 回执文件收口；② CRLF→LF（router.test.js+auth.js，R8 LOW）；③ R5-DC2 中间件最长前缀对齐守卫（item3）；④ 后端 fail-open 收口——conduct/exam-imports 补门控，academic 当时保留 known_drift；⑤ 5 hygiene 路由入 exempt。known_drift 11→3。**Phase 0.7D 已执行（`4002d56`/`bfdbd50`）**：撤销 0.7B「academic 不补门控」——前端三 surface 接 teaching + 后端 /api/v1/academic 补门控，academic-backend-fail-open + teaching-frontend-unwired drift 删除，known_drift 3→1（仅余 studio）；缺 SchoolModule(teaching) 行 pass-through 是全系统既有语义（非 0.7D 引入），设计者 WONTFIX。守卫 --check clean、governance 55+中间件 15 passed、academic 后端+route_snapshot 21 passed、frontend 106 passed、meta-check green。codex-review 状态以机器真源为准（.review-receipts.jsonl；本表只述工作项，不叙述复审轮次 verdict——逐轮叙述每轮都过时并复发 scope_gap）。**Portal Phase 1 解锁=设计者决策**（0.7D 后仅余 studio 已登记 drift + Portal 解锁本身，执行工程师不自解锁）。 |

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
