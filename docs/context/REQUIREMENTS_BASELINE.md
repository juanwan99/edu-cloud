---
title: Requirements Baseline
owner: liang
last_review_date: "2026-06-30"
expiration_in_days: 14
---

# Requirements Baseline

Last refreshed: 2026-06-30 21:05 Asia/Shanghai

This is the current requirements and task-priority baseline for edu-cloud work
under Keel. Older Claude/Codex reports, old plans, old handoffs, Yuanqi task
contracts, and compressed-session summaries are historical evidence only unless
this file or `docs/context/ACTIVE_INDEX.md` explicitly promotes them.

## Source Of Truth

- Current repo: `juanwan99/edu-cloud`
- Current master: `c6e8d8f4f710d84409952f68e1ff3a544a57bac0`
- Current open PRs: none
- Current Keel scopes: 34 closed, 0 active
- Current module dependency gate: `0 edges, 0 cycles`
- Current Keel authority: GitHub required checks, CODEOWNERS, human review, and
  fresh scope files under `control/steward/scopes/`

## User Requirements

1. Deliver real edu-cloud product value. Governance exists only to make delivery
   faster, safer, and less deceptive.
2. Stop silent degradation in security, data integrity, grading, scanning, and
   user-visible AI workflows. Fail closed or surface review-needed states where
   correctness matters.
3. Keep parallel development bounded by Keel scopes. No drive-by edits, no
   hidden scope expansion, no cleanup bundled into unrelated product work.
4. Prefer mature platform gates over local bespoke governance code. Do not add a
   new governance tool unless a GitHub/CI/standard scanner option is insufficient.
5. Keep active docs small, indexed, owner-tagged, review-dated, and subordinate
   to live code, tests, and CI.
6. Use independent review where available, but never treat a model checkbox as
   proof. GitHub checks and human approval are the merge authority.
7. Preserve module isolation. New module edges are disallowed unless explicitly
   scoped, reviewed, and justified.

## Verified Current Facts

- PR #53 and #54 archived unreferenced old plans; `docs/archive/plans/` now has
  56 plan files.
- `docs/plans/` currently has 13 non-placeholder files. Only
  `2026-06-10-db-migration-design.md` and
  `2026-06-10-runtime-foundation-recovery.md` are candidate-active in
  `ACTIVE_INDEX.md`.
- There are 36 non-archive `docs/plans/...` references; 25 of those still point
  to files that are neither live under `docs/plans/` nor present under
  `docs/archive/plans/`.
- PR #71/#73 made OCR review-needed answers fail visible across grading paths.
- PR #75 made grading details-count validation fail closed for flat and nested
  LLM detail formats.
- PR #77 made token revocation fail closed in production with explicit
  environment semantics.
- PR #79 localized the AI chat persistence warning.
- PR #81 hardened Independent Review evidence in PR bodies; PR #82 closed its
  Keel scope.
- All Keel scopes are currently closed; there is no P0 closeout backlog.
- `scripts/pytest_delta.py`, `scripts/truth-doctor.sh`, truth tools,
  guardian/meta scripts, and their related tests/docs are not proven dead. Do
  not delete them without a fresh reachability review across scripts, CI, tests,
  and docs.

## Active Work Queue

### P0 Silent Degradation

Fix these as separate, narrow PRs with fresh scopes and tests:

1. `src/edu_cloud/api/ai.py`: `DataScopeBuilder` failure must not construct a
   wider fallback scope. If AI visibility cannot be built, fail closed or return
   a deny-all scope with explicit user-visible failure.
2. `src/edu_cloud/api/ai.py`: daily chat limit lookup failures must not allow
   unlimited chat. Make quota store/check failure visible and conservative.
3. `src/edu_cloud/workers/grading.py` and
   `src/edu_cloud/modules/grading/router.py`: grading LLM slot lookup exceptions
   must not silently fall back to `.env`/default grading credentials.

### P1 Visible But Still Risky

Investigate and fix after the P0 items, unless the user explicitly promotes one
to P0:

- `src/edu_cloud/modules/scan/pipeline_service.py`: barcode fallback is now
  counted and surfaced, but still continues with filename-derived identity and
  can write official answers.
- `src/edu_cloud/modules/scan/pipeline_service.py`: unknown student numbers are
  marked anomaly and processing continues. Define a quarantine/failed-file
  contract before changing persistence.
- `src/edu_cloud/ai/engine/edu_runtime.py` and
  `src/edu_cloud/ai/providers/coze.py`: chat persistence failure is visible to
  the frontend but still allows the generated answer. Product decision needed:
  acceptable warning state vs hard failure.
- `src/edu_cloud/api/ai.py`: retryable provider errors can switch providers
  without a user-visible provider-switched marker.
- `src/edu_cloud/ai/workflow/engine.py`: failed steps stop a run, but downstream
  skipped steps are not explicitly recorded.
- `src/edu_cloud/modules/grading/gemini_client.py`: cache creation failure falls
  back to no cache. This is cost/performance risk, not correctness P1.

### P3 Hygiene

- Resolve or intentionally document the 25 stale `docs/plans/...` references
- Resolve or intentionally document stale `docs/plans/...` references when a
  touched active/reference doc needs them. Latest sweep found 38 unique
  non-archive plan references, 10 live and 28 missing. Do not make this the main
  product lane.
- `docs/plans/compat-router-deprecation.md` is referenced by live code/tests but
  is missing. Either add a small reference doc or repoint those references.
- Revisit remaining `docs/plans/` files only through `ACTIVE_INDEX.md`
  promotion/reference decisions, not broad deletion.

### Module Decoupling

The machine gate is currently clean: `0 edges, 0 cycles`. Continue to enforce
no new module edges. Do not launch a broad facade refactor from old notes alone;
do targeted boundary work only when a product task exposes a concrete dependency
problem.

Parallel-safe product slices should avoid shared hot spots:

- Safe together: AI DataScope/API safety, scan parser/identity investigation,
  calendar service/API work, grading prompt/rubric algorithm work.
- Do not run together without an explicit coordinator: scan `StudentAnswer`
  schema with grading worker/result changes; module gating/auth/tenant work with
  new router/module-code work; two ORM migration/schema tasks.

## Superseded Baselines

The following are cleared as current requirements:

- Old Yuanqi task contracts and `.yuanqi/**` workflows.
- Loop-engine/local-PS-tool governance designs.
- Old session claims such as "8 remaining plans", "17 broken links", or
  "11 silent degradation items" unless reverified against current master.
- Broad dead-code deletion proposals for guardian/meta/truth/pytest_delta
  scripts.

## Dispatch Rule

Before dispatching a new task, quote the relevant P0/P1/P2 item from this file,
then re-run live commands and line checks. Do not dispatch from memory.
