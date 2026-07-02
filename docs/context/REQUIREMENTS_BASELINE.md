---
title: Requirements Baseline
owner: liang
last_review_date: "2026-07-02"
expiration_in_days: 14
---

# Requirements Baseline

Stable guidance last reviewed: 2026-07-02.

This is the current requirements and task-priority baseline for edu-cloud work
under Keel. Older Claude/Codex reports, old plans, old handoffs, Yuanqi task
contracts, and compressed-session summaries are historical evidence only unless
this file or `docs/context/ACTIVE_INDEX.md` explicitly promotes them.

## Source Of Truth

- Current repo: `juanwan99/edu-cloud`
- Current Keel authority: GitHub required checks, CODEOWNERS, human review, and
  fresh scope files under `control/steward/scopes/`
- Volatile repository facts such as the current master commit, open PRs, CI identifiers,
  latest check status, and active scope counts must be checked live before
  dispatch.
- The module dependency gate must be checked live with
  `python scripts/governance/check_module_dependencies.py --check`.

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
- PR #103 fixed AI chat persistence fail-closed behavior
  (`59503c02` merge; implementation includes `7563f2d4`, `89569e97`,
  `a31a0051`, and `be6607f8`).
- PR #65 fixed truncated grading JSON fail-closed behavior (`e55a4506` merge;
  implementation `520d709c`).
- PR #66 marked uncertain OCR blanks for review-needed (`8e42491c` merge;
  implementation `1f360a0e`).
- PR #71 blocked grading for OCR review-needed answers (`8d5c0d3` merge;
  implementation `ecf5c283`).
- PR #96 fixed short vision grading details fail-closed behavior (`2ab66ea`
  merge; implementation `1b1efa95`).
- PR #92 merged workflow skipped-steps visibility.
- PR #91 merged the active-context refresh after #90.
- PR #90 merged the replacement mainline baseline.
- PR #89 merged the Keel window role-boundary clarification.
- PR #84 merged grading LLM config lookup fail-closed behavior.
- PR #85 merged AI DataScope build-failure fail-closed behavior.
- PR #86 merged scan identity mismatch fail-closed behavior.
- PR #87 merged canonical student identity for adaptive mastery.
- PR #88 merged answer-standardizer text-LLM fallback visibility.
- Merged scope files must not be treated as reusable permission, because PR
  scope validation requires a newly added scope file.
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

1. Merged active scopes are consumed one-time authorizations. Do not chase
   active count to zero routinely; use closeout-only PRs only for explicit
   historical maintenance or compatibility.

### P1 Silent Degradation

Current-master verification on 2026-07-02 removed the old P1 candidates below
from the dispatch queue:

1. `src/edu_cloud/ai/engine/edu_runtime.py`: `_persist_messages()` persistence
   failures are no longer best-effort only. PR #103 (`59503c02` merge) added
   blocking `ai_chat_persistence_failed` handling; current SSE/API tests cover
   the no-usable-answer path when persistence fails.
2. `src/edu_cloud/modules/grading/json_parser.py`: truncated grading JSON is no
   longer repaired into partial output. PR #65 (`e55a4506` merge,
   implementation `520d709c`) removed the old repair behavior; current
   `json_parser.py` documents that truncated JSON is intentionally not repaired,
   and `test_truncated_json_returns_none` covers the behavior. PR #96
   (`2ab66ea` merge) also closes short vision grading details.
3. `src/edu_cloud/modules/grading/ocr_validator.py`: OCR English commentary and
   missing blanks are marked review-needed instead of `unanswered`. PR #66
   (`8e42491c` merge) added review-needed marking, and PR #71 (`8d5c0d3`
   merge) blocks grading paths from consuming review-needed OCR output.

No confirmed P1 item remains open from the old list. Reverify any future P1
candidate against current master before dispatch.

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
