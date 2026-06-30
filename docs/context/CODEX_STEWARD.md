---
title: Codex Stewardship
owner: liang
last_review_date: "2026-06-30"
expiration_in_days: 30
---

# Codex Stewardship

Date: 2026-06-28
Purpose: stable planning memory for how Codex leads edu-cloud under Keel.

## Authority

- Codex is the local steward for planning, implementation help, review,
  hygiene, scope discipline, and acceptance evidence.
- Claude may be used by the user as planner, reviewer, or executor, but no
  model accepts its own work as complete.
- GitHub is the merge authority: required checks, CODEOWNERS, and human review
  decide whether a PR may merge.
- `AGENTS.md` is the active project entrypoint.
- `docs/context/ACTIVE_INDEX.md` controls which docs are active,
  candidate-active, reference, or historical.

## Role Split

Default operating mode:

- Codex is the steward: keep the task queue, scope, evidence contract, PR
  readiness, and final acceptance aligned.
- Claude is auxiliary: use it for manual Claude App review, targeted `claude -p`
  review, investigation, or implementation when explicitly assigned.
- GitHub remains the hard gate; the user remains the only final merge authority.

Do not spend Claude budget by default. Use this escalation ladder:

1. Low-risk closeout or docs-only PR: Codex review plus GitHub gates is enough.
2. Normal business fix: one non-author Independent Review with evidence in the
   PR conversation or review body.
3. High-risk work (grading, auth, tenant/data isolation, runtime, migrations,
   governance gates, deletion/retirement): Codex review plus Claude manual App
   review or `claude -p` if budget allows.

If Claude budget is constrained, the user may run Claude App manually and paste
the review report. That counts as Claude evidence only when the report includes
the exact PR or diff range, checked files, findings, and PASS/FAIL.

The user is not responsible for formatting review evidence. If the user pastes
raw Claude App output, Codex must decide whether it is sufficient, extract the
checked files/findings/verdict, post a concise PR comment, and update the PR
body. If the raw review is missing a clear PASS/FAIL or the reviewed PR/commit,
Codex asks for only that missing fact.

## Keel Working Contract

For governed PRs:

1. Use a separate git worktree for parallel or risky work.
2. Add one new scope file under `control/steward/scopes/`.
3. Keep edits inside the declared `allowed_paths` and outside
   `forbidden_paths`.
4. Put `Steward-Scope: <scope_id>` in the PR body.
5. Let GitHub required checks and CODEOWNER review decide merge readiness.

The retired Yuanqi task-contract workflow is historical evidence only. Do not
create Yuanqi task windows, `.yuanqi/tasks`, or `Yuanqi-Task:` PR markers unless
the user explicitly revives a specific historical fact for analysis.

## Working Memory

- Current facts live in `docs/context/NOW.md`.
- Governance model lives in `docs/context/GOVERNANCE_MODEL.md`.
- Parallel development policy lives in `docs/context/PARALLEL_DEVELOPMENT.md`.
- Long-term module-boundary direction lives in
  `docs/governance/foundation-boundaries.md`.

Durable project memory belongs in tracked `docs/context/**` and
`docs/governance/**`, not ignored local `.codex/` state.

## Planning Checklist

Before non-trivial edu-cloud work:

1. Run `scripts/codex-check` when available.
2. Inspect `git status --short --branch`.
3. Read `docs/context/NOW.md` and `docs/context/ACTIVE_INDEX.md`.
4. Identify module-boundary, runtime, DB, auth, workflow, or deployment risk.
5. For multi-window work, classify the task using
   `docs/context/PARALLEL_DEVELOPMENT.md`.
6. For governed PRs, create the Keel scope file before protected edits.
7. Verify with focused local checks, then rely on GitHub required checks and
   human review for merge authority.

## Dispatch Review

Codex Dispatch Review is required before launching any multi-worker batch,
deletion or retirement task, governance change, central-context change, or
protected-path change.

The `steward/dispatch-review` GitHub check makes this non-optional for PRs:
it rejects stale branches, retired `batch/*` branch names, missing Dispatch
Review evidence, placeholder CDR evidence, and unchecked Dispatch Review
checklist items.

The dispatch review must produce:

1. task mode and whether parallelism is allowed;
2. dependency order between workers or PRs;
3. one scope id per governed PR;
4. exact `allowed_paths` and `forbidden_paths`;
5. local verification commands each worker must run before pushing.

The PR body must cite that review with
`Codex-Dispatch-Review: <CDR-id-or-GitHub-comment-url>`. The implementer must
not invent this value; it comes from the non-implementing steward/reviewer before
implementation starts.

For file deletion or retirement, the review must include reachability evidence
from `git grep` or equivalent across `scripts/`, `tests/`, `.github/workflows/`,
active docs, and governance registries. A file still referenced by those
surfaces is not dead; first update or retire the contract that references it.

## Independent Review

Independent Review happens after implementation and before merge. It checks
whether the code actually solves the problem on the production call path.

Minimum evidence:

1. reviewer identity or source (Codex, Claude App, `claude -p`, or human);
2. commit, PR, or diff range reviewed;
3. files and call paths inspected;
4. test and CI evidence inspected;
5. explicit `PASS` or `FAIL`.

Use the smallest review that protects quality:

- Tier 1: docs-only, closeout-only, and low-risk hygiene PRs need CI plus Codex
  evidence. Claude review is optional.
- Tier 2: ordinary business fixes need one non-author review focused on the
  production call path.
- Tier 3: grading, auth, tenant/data isolation, runtime, migrations,
  governance gates, deletion/retirement, and silent-downgrade fixes need Codex
  review plus Claude App or `claude -p` review when budget allows.

For any new protection field, status, parameter, fallback, or fail-closed flag,
the review must name the production consumer. Examples: `needs_review`,
`ocr_status`, `expected_details_count`, `review_required`, `fail_closed`.
If there is no production consumer, the review must FAIL or mark the PR
incomplete.

Empty GitHub approve bodies, self-authored checklist text, and PR body claims
are not Independent Review evidence.
