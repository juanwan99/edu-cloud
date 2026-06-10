# NOW

Last refreshed: 2026-06-10 18:20 Asia/Shanghai

Use live commands for volatile values such as exact `HEAD`, ahead/behind count,
and active grading-task progress:

```bash
scripts/codex-context --no-network
scripts/meta-check --json --strict --task "current user task"
scripts/guardian-watch --once --no-network --no-model-review
scripts/truth-status.sh /home/ops/projects/edu-cloud
scripts/truth doctor --json
```

## Current Facts

- Branch: `feat/module-governance-repair`
- Upstream: none
- Production URL: `https://mcu.asia`
- Backend API: `127.0.0.1:9000`
- Frontend artifact path: `frontend/dist/`
- Known pytest baseline entries: 26 in `.quality/known-pytest-failures.txt`
- Source HEAD (2026-06-10): `6f90994` (docs-only on code-effective `41a8ced`;
  `git diff HEAD -- src/` clean). All three runtime surfaces now align on HEAD
  `6f90994` with `source_dirty=false`: backend `/api/v1/version`,
  `frontend/dist/version.json`, and nginx `https://mcu.asia/version.json`.
  `scripts/truth-status.sh` exits 0 with no `BROKEN AT:` line. The earlier
  docs-only false `BUILD_DRIFT` is cleared (dist rebuilt on HEAD `6f90994`).
- Backend process (2026-06-10, post-takeover): under **systemd**
  `edu-cloud.service` = **active**, PID `4017244` (booted 2026-06-10 18:17:14),
  runs HEAD `6f90994`, `source_dirty=false`, owns `127.0.0.1:9000`. The prior
  orphan manual uvicorn PID `391900` (`ebf7934`) was stopped; no SERVICE_BYPASS /
  GHOST_PROCESS / PORT_OWNER_MISMATCH (guardian-watch red=0).
- DB doctor is **green** (2026-06-10): `HARD=0 WARN=0` ("No drift detected").
  Migration `a1b2_chat_msgs → e1f2_import_sess` applied via `scripts/db_migrate`
  (backup → dry-run → `db_doctor --strict` → real upgrade; pre-migration backup
  `backups/edu_cloud_20260610_181416_pre_migrate.db`). `exam_import_sessions`
  (16 cols) now exists; `alembic current = e1f2_import_sess (head)`.
- `_audit_log` is NOT a stray leftover: it is an intentional **trigger-backed**
  audit table (6330 rows of `old_data` snapshots for `grading_results` +
  `student_answers`, plus a `_audit_log_cleanup` trigger). Disposition applied =
  **KEEP + allowlist** in `scripts/db_doctor.py` (`ALLOWLIST_TABLES`), **never
  drop** — dropping it destroys data and breaks 4 triggers.
- Runtime services (2026-06-10): `edu-cloud.service` **active** (systemd-managed
  backend), `edu-cloud-worker.service` + `edu-cloud-guardian.service` active.
  Backend is now systemd-managed — do not hand-launch a manual uvicorn.
- Full 2026-06-10 runtime foundation evidence + recovery decision:
  `docs/plans/2026-06-10-runtime-foundation-recovery.md`.
- DB migration + runtime takeover **design / runbook** (order, verify commands,
  rollback points, risk register, Portal unlock gating):
  `docs/plans/2026-06-10-db-migration-design.md`.

## Truthline

The latest verified delivery path is:

- tracked source clean
- frontend build inputs clean
- `frontend/dist/version.json` has `source_dirty=false`
- `https://mcu.asia/version.json` matches local `frontend/dist/version.json`
- backend `/api/v1/version` matches the same git hash

Run `scripts/truth-status.sh /home/ops/projects/edu-cloud` for the live hash.
Any `BROKEN AT:` diagnosis exits non-zero and blocks completion evidence.

## Runtime Foundation Status (2026-06-10) — R1 EXECUTION WINDOW DONE

The R1 takeover execution window (Yuanshou V2 contract `yc-20260610-a2979c86`)
ran the `docs/plans/2026-06-10-db-migration-design.md` runbook. All three standing
blockers are now **CLEARED**; source/build/nginx/backend all aligned on HEAD
`6f90994`:

1. **Backend stale / orphan uvicorn / service inactive** — **CLEARED.** Orphan
   PID `391900` stopped; `edu-cloud.service` taken over by systemd (active,
   PID `4017244`, HEAD `6f90994`, `source_dirty=false`, owns :9000). guardian-watch
   red=0, no SERVICE_BYPASS / GHOST_PROCESS / PORT_OWNER_MISMATCH.
2. **DB schema drift** — **CLEARED.** `scripts/db_migrate` applied
   `a1b2_chat_msgs → e1f2_import_sess` (creates `exam_import_sessions`); `_audit_log`
   allowlisted in `scripts/db_doctor.py`. db_doctor `HARD=0 WARN=0`. Pre-migration
   backup `backups/edu_cloud_20260610_181416_pre_migrate.db` retained. **Execution
   note:** the allowlist had to precede the migration — `db_migrate`'s internal
   `db_doctor --strict` dry-run treats the `_audit_log` orphan as HARD, so the
   design's Step-1-then-Step-2 order was reversed (both in-scope, root cause
   unchanged).
3. **Context stale** — corrected by this refresh (NOW.md now at the post-takeover
   state).

**Portal C1 (DB red→green) + C2 (backend+dist+nginx at HEAD) are now GREEN.**
Remaining for Portal Phase 1 unlock: re-confirm C3 (online module-gating /
portal-services fail-closed) and **designer sign-off** (executor does not
self-unlock). Runbook + rollback points:
`docs/plans/2026-06-10-db-migration-design.md`.

## Current Role-Entry Work

- Active plan: `docs/superpowers/plans/2026-05-26-role-entry-full-optimization.md`.
- Product direction: permission remains the access-control truth; role-entry
  policy decides primary versus secondary UI visibility for the active identity.
- Current known frontend test debt: the full Vitest suite still has historical
  static assertion failures in marking/review tests; role-entry targeted tests
  should be used for this batch, plus `scripts/codex-verify frontend`.

## Module Governance Phase 0.5 + 0.6 (2026-06-06)

Branch `feat/module-governance-repair`. Module governance extended from static
reconciliation (0.5) to runtime direct-URL gating (0.6).

Phase 0.5 — static module-semantics guard:
- Guard `scripts/governance/check_module_semantics.py`; truth
  `docs/governance/module-semantics.yaml`; tests
  `tests/governance/test_module_semantics.py`.
- `748587c` — MED: route-field moduleCode parser made order-insensitive.
- `1cb7de7` — R1 HIGH: unregistered + no-moduleCode route on a gating surface
  no longer escapes fail-closed; truth declares `/` as null (denominator).

Phase 0.6 main body — runtime hardening (4 commits, resolves R2/R3 findings):
- `f51342a` — drift fail-closed: `check_frontend_drift` uses the still-holding
  `_FRONTEND_DRIFT_PROBES` set as denominator; deleting a still-true drift row
  (studio/teaching) now fails.
- `8606ac6` — authGuard direct-URL module gating (initial): roles/permissions
  pass → gate by `enabledModules`; disabled module → `next('/')`.
- `bd8be46` — R3 fixes: dynamic routes (`/exams/:id`) gated via
  `to.meta.moduleCode` fallback; school users fail-closed (module state must be
  loaded AND moduleCode in the enabled list, else block); admin (no `school_id`)
  exempt; `loadModules` API failure returns empty list (not default 4).

Evidence: `tests/governance` 166 pass; `check_module_semantics.py --check`
clean; `router.test.js` 41 pass (9 module-gating); `auth-store.test.js` 17 pass;
full vitest 2483 passed / 3 pre-existing failures (marking/review static
assertions, unrelated — verified by stash).

Review status: `codex-review f82df2a..HEAD` previously reached **R4 = FINDINGS
(NOT PASS)**, receipt `engine_review` reviewed_sha `bd8be46`. R4 was carved into
the **Phase 0.6C coverage-completeness** sub-task (designer decision 2026-06-06),
now **implemented** in 3 commits (`70eeac2`/`b1a6d09`/`61ed166`):
- **F-001 HIGH (security) — FIXED** (`70eeac2`): `/profile/student/:studentId`
  补 `moduleCode: study_analytics`（router-meta + module-semantics `fr`）+ 直达
  拦截/放行 router 测试。
- **F-002 MED (root cause) — FIXED** (`b1a6d09`): `check_module_semantics.py`
  将 `router_meta` 升为完整门控面（受控覆盖 + 动态 fail-closed，catch-all 排除）；
  补齐 calendar/error-book/homework/knowledge-tree/question-bank 5 个受控 route
  的 router-meta moduleCode；改写旧豁免锁 R2-A4/#31 + 4 动态门控用例。
- **后端 profile fail-open — FIXED** (`61ed166`): `ROUTE_MODULE_MAP` 加
  `/api/v1/profile → study_analytics`，删 `profile-backend-fail-open` drift。
- **F-003 LOW (NOW staleness) — resolved by this doc-correction commit.**

Local evidence: `check_module_semantics.py --check` clean; `tests/governance`
55 pass; frontend `router.test.js`+`auth-store.test.js` 60 pass; backend
profile suite 29 pass.

R5 re-review (`codex-review range:f82df2a..HEAD`, reviewed_sha `7f4c296`) =
**FINDINGS**: R4 F-001/F-002/F-003 confirmed FIXED (NOT re-reported → 0.6C goal
met). 2 NEW findings, out-of-scope of 0.6C but pre-existing:
- **R5 F-001 = MED `security_design` (NOT a deferrable design_concern)** — engine
  verified frontend module-gating fail-open: `loadModules` marks an empty list as
  loaded, the shared menu-layer predicate `moduleMatches` (`routeAccess.js:46`
  empty-list=allow) + `AppHeader.moduleFallbacks` treat empty/unknown as "no
  filter", so multiple surfaces keep showing disabled-module entries to school
  users. Evidence: `canAccessRouteForRole('school_admin','/grading/tasks',[])=true`.
  authGuard already fail-closes the actual navigation, but the surface itself is a
  fail-open security面缺陷 — **must be fixed in Phase 0.7A, not deferred**.
- R5 F-002 = LOW `design_concern` — guard longest-prefix vs middleware
  dict-first-match drift (knowledge/knowledge-tree both `research`, no impact today).

## Phase 0.7A — frontend module-visibility fail-closed (2026-06-06, implemented)

Resolves R5 F-001. Introduces an explicit **module gate context**
`{exempt, modulesLoaded, enabledModules}` in `routeAccess.js`
(`createModuleGate`/`moduleGateFromAuth`), replacing the overloaded empty array
that conflated 未加载/加载失败/无模块/admin豁免. All four visibility surfaces
(`AppSidebar`/`AppHeader`/`RoleSwitcher`/`DashboardPage`) now derive the gate via
`moduleGateFromAuth(auth)` and share one predicate **mathematically equivalent to
authGuard** (`router/index.js:187-188`): allow IFF
`!school_id (exempt) OR (modulesLoaded && enabledModules.includes(code))`.
School users with modules unknown/failed/empty → module entries fail-closed
hidden; admin/no-school_id keep the exemption. `moduleMatches` is now fail-closed;
`AppHeader.moduleFallbacks` removed; `DashboardPage.moduleEnabled/moduleFallbacks`
(dead code) deleted. authGuard unchanged — surfaces align to it, not weaken it.

Local evidence: targeted frontend `routeAccess`+`AppSidebar`+`AppHeader`+
`RoleSwitcher`+`sidebarConfig`+`auth-store`+`router`+`config`+`DashboardPage`
181 pass; full vitest 2498 pass / 3 pre-existing baseline failures (marking/review
static assertions, unrelated); `tests/governance` 170 pass;
`check_module_semantics.py --check` clean (guard parses declarations, unaffected);
`meta-check --strict` green.

Re-review `codex-review range:f82df2a..HEAD` R6→R8 (commits `2d2bfba`/`369625e`/
`e1ff2e1`/`3f98a30`):
- R6: NEW MED `security_design` — `RoleSwitcher` switch-time current-route check used
  the exact routeAccess table only; dynamic sub-routes (`/exams/:id`) missed the
  module gate → fail-open. Fixed `e1ff2e1` (meta.moduleCode fallback).
- R7: same-root-cause MED — the **permission** dimension of dynamic routes
  (`/exams/:examId/ai-grading/:subjectId` needs `manage_grading`) also fail-open.
  Fixed `3f98a30`: new `canAccessMatchedRoute(role,path,meta,gate)` covering exact
  table ∪ dynamic `route.meta` (permission + module), authGuard-aligned.
- R8: **zero MED/security findings** — Phase 0.7A security goal met. Sole residual =
  1 LOW `defect_fix` (CRLF trailing whitespace in `router.test.js`/`auth.js`,
  **0.6-era files, not 0.7A changes** — `git diff --check 5fad3cc..HEAD` is clean).

## Next Phase

Phase 0.6C **done**; Phase 0.7A (frontend module-visibility fail-closed, R5/R6/R7
MED `security_design`) **done & committed** (`2d2bfba`..`3f98a30`), R8 re-review
zero MED.

Phase 0.7B drift burn-down **done & committed** (`fd89f10`/`0d78f55`/`90c8a93`/
`c989e09`): ① untracked gate receipt committed; ② CRLF→LF on
`router.test.js`+`auth.js` (R8 LOW, content-neutral); ③ R5-DC2 — middleware
matching aligned to the guard's longest-prefix (`resolve_module_code`/
`_longest_prefix_match`, exempt-first); ④ backend fail-open — `/api/v1/conduct`
(conduct) and `/api/v1/exam-imports` (exam) gated; **`/api/v1/academic` kept as
registered `academic-backend-fail-open` drift** — its frontend `/academic/*` is
permission-only (no `moduleCode`, `teaching-frontend-unwired`), so backend-only
gating would 403-break the pages for schools with `manage_scheduling` but
`teaching` disabled; wiring the frontend is out of 0.7B scope ("不改业务 UI");
⑤ hygiene — menus/portal/grades/teachers/client-logs added to `EXEMPT_PREFIXES`
(behaviour-neutral, were already pass-through). `known_drift` 11→3 (academic
backend + studio/teaching frontend). Evidence: guard `--check` clean;
governance+middleware 66 passed; conduct+exam_import 153 passed; meta-check green.
codex-review status lives in the machine source of truth — gate
`code_review_batch_07b` in `docs/plans/2026-06-04-module-governance-repair-gates.json`
plus `.review-receipts.jsonl`. This doc states the *work*; the gate states the
*review verdict* (do not narrate per-round verdicts here — that narration goes
stale every round and re-triggers a scope_gap finding).

Phase 0.7D academic double-sided fail-open **closed** (`4002d56`/`bfdbd50`): frontend
`/academic/*` (teaching-plans/timetable/semesters) wired to `moduleCode: teaching`
across routeAccess/router-meta/sidebar; backend `/api/v1/academic → teaching` in
`ROUTE_MODULE_MAP`. `academic-backend-fail-open` + `teaching-frontend-unwired` drifts
deleted (`_FRONTEND_DRIFT_PROBES` keeps the teaching probe as a regression guard);
`known_drift` 3→1 (only `studio-frontend-entry-missing`). teaching stays out of
`DEFAULT_ENABLED`; middleware 403s when the `SchoolModule(teaching)` row exists &
`enabled=False` — normally-init'd schools have it (`init_school_modules`).

Phase 0.7E absent-row fail-open **closed** (codex-review F-001): the designer reversed the
0.7D WONTFIX and ruled **Option B "system-wide principled fix"**. The dispatch absent-row
default is now the pure helper `module_enabled_default(code,row)`, mirroring the frontend
`get_all_modules` (`services/school_settings_service.py:109` `else (code in DEFAULT_ENABLED)`).
**Present row** — the explicit `enabled` value always wins (behaviour unchanged). **Absent
row** — enabled IFF `code in DEFAULT_ENABLED`, so non-default modules (teaching/research/
study_analytics) with no row now **fail-closed 403**, while DEFAULT_ENABLED modules keep
pass-through. The backend 403 surface and the frontend visibility surface are now a single
source of truth, closing the absent-row fail-open **system-wide** (every gated module, not
just academic). `init_school_modules` seeds all 9 rows for new schools, so normally-init'd
schools are unaffected (present row); only un-backfilled legacy schools with a missing row
are now fail-closed (a security fix, not a regression). teaching stays out of `DEFAULT_ENABLED`.
Evidence: guard `--check` clean; 6 new pure-function unit tests; target suite (5 files) 87
passed; full backend 2481 passed / 22 failed — the 22 are all pre-existing env failures
(socksio/playwright/httpx), **0 module-gating 403s** (`grep 未启用` = 0).
**R1** (codex-review F-001 HIGH test_gap closed): the 6 pure-function tests never exercised
the HTTP dispatch entry — mutating the absent-row default to fail-open left the 87-test target
suite green. Added 4 dispatch regression tests (minimal FastAPI app + `ModuleCheckMiddleware`
+ ASGITransport: absent `SchoolModule(teaching)` row → HTTP 403 / explicit enabled → 200 /
explicit disabled → 403 / DEFAULT_ENABLED absent → 200); the mutation now fails the core test
(catch). Target suite 91 passed (87+4); `28ddbf9`.

**Portal homepage aggregation (Phase 1) = CONDITIONAL UNLOCK** — designer decision
(`sid:a4e5781a`), persisted in
`docs/plans/2026-06-07-phase09-portal-unlock-decision.md`. **Not** unconditional,
**not** KEEP BLOCKED: the source foundation is PASS (Phase 0.8,
`docs/plans/2026-06-07-phase08-acceptance-decision.md`), so the unlock ruling stands,
but **implementation is gated by runtime/DB cleanup** — three conditions must all go
green before any Portal code: ① DB doctor red→green (**GREEN 2026-06-10**: migration
applied, `exam_import_sessions` created, `_audit_log` allowlisted, db_doctor HARD=0
WARN=0); ② deploy/runtime hash aligned to HEAD (**GREEN 2026-06-10**: backend+dist+nginx
all at HEAD `6f90994`, `source_dirty=false`, truth-status no `BROKEN AT:` — see "Runtime
Foundation Status (2026-06-10) — R1 EXECUTION WINDOW DONE"); ③ online-verify module
gating / portal services keep fail-closed (**still to re-confirm + designer sign-off**). First-cut scope: frontend homepage
aggregation + consume existing `/api/v1/portal/*` (5 endpoints live,
`modules/portal/router.py:25-57`) + service cards gated by `moduleGateFromAuth`.
Foundation frozen: do NOT change `DEFAULT_ENABLED` / module middleware / authGuard /
module-semantics. `studio-frontend-entry-missing` drift does not block unlock — close
it only after Portal services actually expose a studio entry. Plan:
`docs/plans/2026-06-06-phase07-drift-burndown.md`. See
`docs/plans/2026-06-06-phase06-coverage-handoff.md` for 0.6C.

## Codex Migration State

Codex-native migration layer is now committed:

- `AGENTS.md`: active Codex entrypoint.
- `docs/context/GOVERNANCE_MODEL.md`: 元守双核心 model.
- `docs/context/META_RUNTIME.md`: Meta Core task-contract runtime.
- `docs/context/**`: current facts, commands, lessons, safety matrix, active
  index, artifact policy, and Claude auxiliary protocol.
- `scripts/codex-context`: current project summary.
- `scripts/codex-check`: read-only start-of-work preflight.
- `scripts/meta-check`: synchronous Meta Core runtime. It emits
  `meta.core.v1` snapshots and can write `logs/meta-state.json` for the latest
  task contract. `scripts/codex-verify full` runs `scripts/meta-check --strict`
  before backend/frontend gates. Deep checks include `--check-drift` for
  baseline obligation loss and `--check-recent-plans` for committed plan
  evidence gaps.
- `scripts/codex-consult-claude`: read-only Claude Code auxiliary reviewer
  wrapper. It injects current `logs/meta-state.json` obligations into the review
  prompt when available.
- `scripts/codex-verify`: completion verification wrapper with `safety`,
  `frontend`, `backend`, `schema`, and `full` modes.
- `scripts/guardian-watch`: realtime Guardian Core runtime. It emits
  `guardian.watch.v1` snapshots and can run continuously from
  `deploy/systemd/edu-cloud-guardian.service`.
- `.github/workflows/test.yml`: governance, backend, and frontend CI smoke.

The governance model is formally **元守双核心**:

- Meta Core / 元控核: owns direction, facts, task boundaries, context, Claude
  read-only counter-review, and the completion evidence contract.
- Guardian Core / 守护核: owns dirty state, truthline, DB/migration gates,
  safety scanning, frontend/backend build-runtime consistency, and environment
  hygiene.

Meta runtime boundary:

- allowed: classify active-context, NOW freshness, lesson, registration,
  Claude-boundary, changed/recent plan evidence, and task-obligation drift
- allowed: write `logs/meta-state.json` when explicitly run with
  `--write-state`
- forbidden: auto-edit files, override user instructions, let Claude/GPT claim
  completion, run builds/migrations/deploys, or replace Guardian realtime
  monitoring

Guardian realtime runtime boundary:

- allowed: observe, classify, write `logs/guardian-state.json`, append
  `logs/guardian-watch.jsonl`, and schedule rate-limited read-only Claude
  reviews through `scripts/codex-consult-claude`
- forbidden: auto-kill workers/services/Claude sessions, auto-delete
  DB/WAL/SHM/dirty source/experiment data, run git cleanup, run migrations,
  build, or deploy

## AI Grading State

The AI grading prompt/rubric/guard changes are committed. Targeted AI grading
tests have no new failures; the remaining prompt test failure is part of the
known baseline.

Live grading jobs can run for hours. A legacy shell-started ARQ worker may still
be processing jobs started before `edu-cloud-worker.service` was installed. Do
not kill it unless you accept ARQ cancellation/retry risk; after it drains,
stop the legacy process and rerun `scripts/truth doctor --json`.

## Artifact State

Local experiment and runtime artifacts are ignored rather than committed:

- active SQLite WAL/SHM files, classified as runtime state by `codex-context`
- stale migration lock files
- `.codex` and `frontend/.codex`
- backups and screenshots
- local AI grading experiment data/scripts listed in `ARTIFACT_POLICY.md`

Do not copy active SQLite databases with `cp` or `rsync`.

## Do Not Do

- Do not clean ignored artifacts blindly.
- Do not overwrite AI grading source changes from older handoffs.
- Do not run direct Alembic migration commands.
- Do not copy active SQLite DB files.
- Do not use old Windows-era docs as current facts.
