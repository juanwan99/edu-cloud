# edu-cloud Foundation Boundaries

> Date: 2026-06-04
> Purpose: freeze the current governance foundation before adding portal-style
> homepage aggregation, service center, business-system center, todo/message,
> or personal workspace features.

## Current Governance Baseline

- Module contracts are the source of truth for generated governance artifacts:
  `src/edu_cloud/modules/*/MODULE.md` -> `docs/governance/modules.yaml`,
  `dependency-graph.md`, and `debt-report.md`.
- Current module count is 23. `exam_import` is registered, the backend
  `portal` aggregation module is present, and the debt report is clean.
- Generated module dependency graph is still cyclic. The negative-delta gate is
  `docs/governance/module-dependencies.yaml`, checked by
  `scripts/governance/check_module_dependencies.py --check`.
- Current actual cross-module import baseline: 0 edges and 0 cycles (the
  historical 55 edges / 30 cycles were cleared by D-03R on 2026-06-22; see
  debt-ledger.md). New edges or new cycles are not allowed.
- Cross-domain governance debt (process + structural) is tracked in the
  **foundation debt ledger**: `docs/governance/debt-ledger.md` — single source
  for open R-H3/R-H4/R-H5 risks, the 55-edge/30-cycle burn-down, runtime
  operation / review receipt process holes, AI tool module_code debt,
  `known_drift`=studio, and Portal Phase 1 unlock preconditions. Window topic
  selection is ledger-driven; new debt is registered there first.

## Long-Term Architecture Direction

- Target shape: modular monolith first. Split services or repos only after
  module contracts, ownership, and runtime boundaries are stable.
- The historical 55 cross-module edges / 30 cycles have been cleared to 0/0
  (D-03R). Keep the baseline flat at 0; do not add new edges or cycles.
- Prefer module-owned APIs, service facades, domain events, or explicit
  contract files over direct imports into another module's internals.
- Cross-module integration must be justified in the plan or evidence and paired
  with a guard/test update when it changes architectural risk.
- No new dependency cycle without explicit designer approval.
- Strategic goal: increase safe parallelism so separate execution windows can
  work by module or scope without hidden global side effects.
- Operational rule: use `docs/context/PARALLEL_DEVELOPMENT.md` to classify
  whether a task is read-only, docs-only, module-writer, frontend-only, or
  exclusive before starting another execution window.

## Permissions Boundary

- Backend source: `src/edu_cloud/core/permissions.py`.
- Frontend mirror: `frontend/src/config/permissions.js`.
- Backend roles: 16.
  `academic_director`, `admin`, `district_admin`, `exam_coordinator`,
  `grade_leader`, `head_teacher`, `homeroom_teacher`, `lesson_prep_leader`,
  `observer`, `parent`, `platform_admin`, `principal`, `school_admin`,
  `subject_teacher`, `teacher`, `teaching_research_leader`.
- Frontend canonical roles: 11.
  `academic_director`, `district_admin`, `grade_leader`, `homeroom_teacher`,
  `lesson_prep_leader`, `parent`, `platform_admin`, `principal`,
  `school_admin`, `subject_teacher`, `teaching_research_leader`.
- Permission values are aligned at 37 values on both sides, and canonical
  role permission matrices are checked by
  `scripts/governance/check_permission_mirror.py`.
- Governance risk: role aliases and operational roles exist in backend but are
  not all modeled in frontend. Portal aggregation must not invent role logic in
  page components; it should consume a normalized role/permission contract.

## School Module Switch Boundary

- Source: `src/edu_cloud/models/school_settings.py`.
- Module codes: `exam`, `grading`, `homework`, `study_analytics`, `research`,
  `teaching`, `calendar`, `studio`, `conduct`.
- Default enabled: `calendar`, `conduct`, `exam`, `grading`, `homework`,
  `studio`.
- Governance risk: frontend route `moduleCode` values and AI tool
  `module_code` values should be checked against this catalog before a portal
  app registry is introduced.

## AI Tool Boundary

- Source: `src/edu_cloud/ai/engine/tools/*.py`.
- Baseline: `docs/governance/ai-tool-module-codes.yaml`, checked by
  `scripts/governance/check_ai_tool_modules.py`.
- Current module_code counts: `exam` 46, `conduct` 9, `homework` 6,
  `grading` 3, `research` 3.
- Current AI tool count: 67. All tool `module_code` values are valid
  `MODULE_CODES`; tool additions/removals or ownership changes require an
  explicit baseline update after review.
- Known drift: many analytics/profile/bank/knowledge/student-facing tools are
  currently gated by `module_code="exam"`. This is an existing semantic debt.
- Governance rule for future work: no new AI tool should be added without an
  explicit module owner and module switch mapping. Reclassifying existing tools
  should be done in a focused batch with role/scope tests.

## Notification / Calendar / Approval / Workflow Boundary

- Portal contract: `docs/governance/portal-aggregation-contract.md`, guarded by
  `tests/governance/test_portal_contract.py`.
- Notification list API: `src/edu_cloud/api/notifications_api.py`,
  `/api/v1/notifications`.
- Calendar API: `src/edu_cloud/modules/calendar/router.py`,
  `/api/v1/calendar`.
- Notification tables: `notifications`, `notification_rules`,
  `conduct_notifications`.
- Calendar table: `calendar_events`.
- Approval tables: `approval_flows`, `approval_steps`.
- Workflow tables: `workflow_runs`, `workflow_steps`.
- Studio notification approval flow currently owns document transition and
  approval-chain behavior; calendar owns calendar events and notification
  rules; conduct owns parent-facing conduct notifications.
- Governance risk: these pieces are useful portal ingredients. The backend
  `portal` module now exposes the first `/api/v1/portal/*` aggregation APIs,
  and the frontend homepage should migrate to those APIs before adding richer
  portal features.

## Next Governance Batches

Batch selection is driven by `docs/governance/debt-ledger.md` (risk × batch
size × parallelizability), not by individual findings.

1. Move the frontend homepage/workbench reads to `/api/v1/portal/*` instead of
   calling business modules one by one.
2. Reclassify existing AI tools whose domain/module pairing is semantically
   overloaded by `exam`, with role/scope tests in the same batch
   (ledger entry D-04).
