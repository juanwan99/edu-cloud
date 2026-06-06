# NOW

Last refreshed: 2026-05-26 23:16 Asia/Shanghai

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

- Branch: `codex/role-permission-phase2`
- Upstream: none
- Production URL: `https://mcu.asia`
- Backend API: `127.0.0.1:9000`
- Frontend artifact path: `frontend/dist/`
- Known pytest baseline entries: 26 in `.quality/known-pytest-failures.txt`
- Current live hash: `d9b1c56`
- Truthline at 2026-05-26 23:16 Asia/Shanghai: source, frontend build,
  nginx, and backend are aligned on `d9b1c56`.
- DB doctor is currently red: ORM declares `exam_import_sessions`, but the DB
  has no such table; DB also contains orphan table `_audit_log`.
- Runtime services: `edu-cloud.service` and `edu-cloud-worker.service` are
  active at the live hash.
- `edu-cloud-worker.service` is installed and enabled from
  `deploy/systemd/edu-cloud-worker.service`.

## Truthline

The latest verified delivery path is:

- tracked source clean
- frontend build inputs clean
- `frontend/dist/version.json` has `source_dirty=false`
- `https://mcu.asia/version.json` matches local `frontend/dist/version.json`
- backend `/api/v1/version` matches the same git hash

Run `scripts/truth-status.sh /home/ops/projects/edu-cloud` for the live hash.
Any `BROKEN AT:` diagnosis exits non-zero and blocks completion evidence.

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

Phase 0.6 — runtime hardening (resolves both R2 review findings):
- `f51342a` — F-002: `check_frontend_drift` now uses the still-holding
  `_FRONTEND_DRIFT_PROBES` set as a fail-closed denominator; deleting a
  still-true drift row (studio/teaching) now fails.
- `8606ac6` — F-001: `authGuard` (`frontend/src/router/index.js`) now gates
  direct URLs by `enabledModules`. After roles/permissions pass it reads the
  moduleCode from `routeAccess.js` (the sidebar gating truth) and applies
  `moduleMatches`; fail-closed `await loadModules()` when not yet loaded;
  disabled module → `next('/')`. routeAccess.js covers all 14 controlled
  routes, so router_meta stays a documentation surface (no GATING_SURFACES
  change needed).

Evidence: `tests/governance` module-semantics 51 pass;
`check_module_semantics.py --check` clean; frontend `router.test.js` 37 pass
(5 new module-gating); full vitest 2478 passed / 3 pre-existing failures
(marking/review static assertions, unrelated — verified by stash).

Final review: NOT yet re-run after Phase 0.6. MUST run
`codex-review code f82df2a..HEAD` and reach PASS before Phase 0.5/0.6 can be
declared complete.

## Next Phase

Phase 0.6 close-out: re-run codex-review to PASS — only then is this the
auditable foundation. Portal homepage aggregation (聚合合同) is a LATER phase
(Phase 1); do NOT enter Portal or absorb portal business code until the 0.6
review PASSES.

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
