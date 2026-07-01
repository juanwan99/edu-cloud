---
title: Requirements Baseline
owner: liang
last_review_date: "2026-07-01"
expiration_in_days: 14
---

# Requirements Baseline

Last refreshed: 2026-07-01 09:51 Asia/Shanghai

This is the current requirements and task-priority baseline for edu-cloud work
under Keel. Older Claude/Codex reports, old plans, old handoffs, Yuanqi task
contracts, and compressed-session summaries are historical evidence only unless
this file or `docs/context/ACTIVE_INDEX.md` explicitly promotes them.

## Source Of Truth

- Current repo: `juanwan99/edu-cloud`
- Current master: `2695793fd719dd728099ccb63b929e55ecbb79d2`
- Current open PRs: #90, this replacement baseline PR. Before #90 was opened,
  there were no open PRs after stale #83 was closed.
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

- PR #83 was closed as stale after #84-#89 changed the baseline it described.
- PR #89 merged the Keel window role-boundary clarification.
- PR #84 merged grading LLM config lookup fail-closed behavior.
- PR #85 merged AI DataScope build-failure fail-closed behavior.
- PR #86 merged scan identity mismatch fail-closed behavior.
- PR #87 merged canonical student identity for adaptive mastery.
- PR #88 merged answer-standardizer text-LLM fallback visibility.
- Current Keel scope files on `origin/master` are 34 closed and 6 active. This
  PR branch adds one active scope for its own review, so branch-local scope
  count is 34 closed and 7 active until merge. The master active files are the
  merged #84-#89 scopes and should not be treated as reusable permission,
  because PR scope validation requires a newly added scope file.
- Latest master `Tests` run for #88 is still in progress at refresh time; do not
  claim current master is fully green until that run completes.
- PR #53 and #54 archived unreferenced old plans; `docs/archive/plans/` now has
  56 plan files.
- `docs/plans/` currently has 13 non-placeholder files. Only
  `2026-06-10-db-migration-design.md` and
  `2026-06-10-runtime-foundation-recovery.md` are candidate-active in
  `ACTIVE_INDEX.md`.
- There are 36 non-archive `docs/plans/...` references; 25 of those still point
  to files that are neither live under `docs/plans/` nor present under
  `docs/archive/plans/`.
- `scripts/pytest_delta.py`, `scripts/truth-doctor.sh`, truth tools,
  guardian/meta scripts, and their related tests/docs are not proven dead. Do
  not delete them without a fresh reachability review across scripts, CI, tests,
  and docs.

## Active Work Queue

### P0 Keel Queue

1. Wait for current master `Tests` after #88 to finish before making a fully
   green-mainline claim.
2. If desired, close or retire the six merged active scope files from #84-#89 in
   a dedicated scope-closeout PR. Do not bundle this with product behavior work.

### P1 Silent Degradation

The following old candidates must be reverified against current master before
dispatch. Fix only confirmed issues as separate, narrow PRs with fresh scopes
and tests:

1. `src/edu_cloud/ai/engine/edu_runtime.py`: `_persist_messages()` still treats
   chat persistence as best-effort and only logs DB write failures.
2. `src/edu_cloud/modules/grading/json_parser.py`: `_repair_truncated()` can
   close incomplete JSON and return repaired grading output. It has an
   incomplete-result guard, but the repair path is still a correctness risk.
3. `src/edu_cloud/modules/grading/ocr_validator.py`: OCR English commentary and
   missing blanks can become `unanswered` text. Prefer explicit review-needed or
   unable-to-recognize states over silently treating uncertainty as no answer.

### P2 Visible But Still Risky

Investigate only after P1 and reverify before dispatch:

- `src/edu_cloud/modules/scan/pipeline_service.py`: barcode fallback is now
  counted and surfaced, but still continues with filename-derived identity.
- `src/edu_cloud/modules/scan/pipeline_service.py`: unknown student numbers are
  marked anomaly and processing continues. Decide whether this should block.
- `src/edu_cloud/ai/workflow/engine.py`: failed steps stop a run, but downstream
  skipped steps are not explicitly recorded.
- `src/edu_cloud/modules/grading/gemini_client.py`: cache creation failure falls
  back to no cache. This is cost/performance risk, not correctness P1.

### P3 Hygiene

- Start document lifecycle cleanup as its own lane: keep `ACTIVE_INDEX.md`
  authoritative, update active-doc review metadata, and reduce stale docs from
  the default agent context.
- Resolve or intentionally document the 25 stale `docs/plans/...` references
  when a touched active/reference doc needs them. Do not make this the main
  product lane.
- Revisit remaining `docs/plans/` files only through `ACTIVE_INDEX.md`
  promotion/reference decisions, not broad deletion.

### Module Decoupling

The machine gate is currently clean: `0 edges, 0 cycles`. Continue to enforce
no new module edges. Do not launch a broad facade refactor from old notes alone;
do targeted boundary work only when a product task exposes a concrete dependency
problem.

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
