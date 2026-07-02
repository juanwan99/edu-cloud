---
title: Codex Stewardship
owner: liang
last_review_date: "2026-07-02"
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
For non-draft governed PRs, the PR body is the canonical merge-time evidence
slot: `Reviewer / evidence URL` must point to the review evidence and `Verdict`
must be `PASS`. The approving GitHub review should repeat that evidence URL in
its body so the approval is traceable without reading the whole conversation.

## Keel Working Contract

For governed PRs:

1. Use a separate git worktree for parallel or risky work.
2. Add one new scope file under `control/steward/scopes/`.
3. Keep edits inside the declared `allowed_paths` and outside
   `forbidden_paths`.
4. Put `Steward-Scope: <scope_id>` in the PR body.
5. Let GitHub required checks and CODEOWNER review decide merge readiness.

The scope file is a one-time PR authorization, not a durable task state that
must be reset after merge. Do not reuse a merged scope file for new work. The
active lifecycle boundary is the fresh scope file newly added in the PR plus an
`expires_at` that remains in the future. Closeout-only PRs remain compatible for
historical maintenance, but they are not the daily flow.

Legacy Yuanqi paths are a gate-level default forbidden set. Scope files do not
need to hand-copy `.yuanqi/`, `scripts/yuanqi/`, or `tests/yuanqi/` into
`forbidden_paths`. Additions and modifications there stay blocked, and
`allowed_paths` must not name them. Deletions of legacy Yuanqi files are exempt
from changed-file enforcement so cleanup can proceed without being treated as a
revival.

The retired Yuanqi task-contract workflow is historical evidence only. Do not
create Yuanqi task windows, `.yuanqi/tasks`, or `Yuanqi-Task:` PR markers unless
the user explicitly revives a specific historical fact for analysis.

## Scope Lifecycle RCA

The ceremony came from storing lifecycle state in Git, running the same full
gate shape for every PR, requiring global forbidden paths to be copied into each
scope, and not asking which extra risk a new governance action actually closed.
Keel keeps the useful boundary checks: a fresh scope file, future `expires_at`,
default legacy Yuanqi quarantine in the gate, focused dispatch review, and
GitHub review for merge authority.

## Integration Lanes

Keel does not build its own scheduler, merge train, or durable queue state.
Reuse mature GitHub surfaces first: repository rulesets, required checks,
CODEOWNERS, PR reviews, and GitHub Projects for lightweight visibility. GitHub
Merge Queue is a candidate mature tool only when the repository owner type,
GitHub plan, ruleset, and `merge_group` workflow support are all confirmed.

Every mutating batch must classify each governed PR into one integration lane:

- `independent`: non-overlapping work that can be implemented and reviewed in
  parallel. It does not need to chase unrelated master merges unless GitHub
  checks or review evidence require a refresh.
- `guarded`: higher-risk work such as silent-downgrade cleanup, grading,
  auth-adjacent changes, shared facades, and module-boundary changes. It may be
  implemented in parallel only when paths and dependencies are explicit. It
  remains draft until checks and deep review evidence are complete.
- `exclusive`: governance gates, rulesets, workflows, central context, DB,
  runtime, deploy, auth core, and permission core. Use one mutating writer and
  one integration decision at a time.

The steward owns lane assignment. Workers own only the scoped implementation
they were assigned. If a worker discovers that the chosen lane is wrong, it
stops and asks the steward to re-dispatch instead of widening scope.

## Worker Dispatch Profiles

Keel uses worker profiles to keep implementation attention away from the
steward without giving workers open-ended authority.

- `read_only_reviewer`: may inspect and report only. Existing
  `scripts/codex-consult-claude` is the default wrapper for Claude review.
- `windows_no_shell_worker`: may edit only the paths named in the startup
  packet, using native Claude file-tool permissions. It must not receive shell
  or local test authority. The steward or CI verifies.
- `wsl2_sandbox_worker`: reserved for work that truly needs shell or test
  authority. Do not claim native Windows no-shell mode is equivalent to this
  operating-system boundary.

For every mutating worker, Codex must issue a startup packet with the worktree,
branch, scope id, lane, allowed write paths, read-only contract paths, forbidden
central paths, test authority, draft PR permission, CI self-fix permission, and
stop condition. Worker prompts may refine the implementation, but they do not
override that packet. Boundary changes require a fresh steward dispatch.

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
2. integration lane: `independent`, `guarded`, or `exclusive`;
3. dependency order between workers or PRs;
4. one scope id per governed PR;
5. exact `allowed_paths` and `forbidden_paths`;
6. local verification commands each worker must run before pushing;
7. the requested write license terms: which scopes may create draft PRs, whether
   CI self-fix is allowed, and when workers must stop.

The PR body must cite that review with
`Codex-Dispatch-Review: <CDR-id-or-GitHub-comment-url>`. The implementer must
not invent this value; it comes from the non-implementing steward/reviewer before
implementation starts.

Dispatch Review decides that a task is bounded enough to write; it does not
itself perform the user write approval. Before mutating workers start, the
steward must present the batch and obtain a clear write license. The write
license is required for branch creation, commits, pushes, draft PR creation, PR
body edits, GitHub comments, review requests, ready-for-review transitions, and
PR closure. If the user says "investigate", "plan", "review", or anything else
that does not clearly approve writes, keep the work read-only.

Default worker stop rule: after opening the first draft PR, stop and report. If
CI, `steward/dispatch-review`, `steward/pr-scope`, semgrep, CodeQL, or frontend
/ backend tests fail, the worker reports the failing check and waits. A fix push
is allowed only when the write license explicitly included CI self-fix for that
scope, or when the steward/user issues a targeted follow-up.

Integration lane stop rules:

- `independent`: stop after draft PR and required local evidence. The steward
  may keep other independent PRs moving while checks run.
- `guarded`: stop after draft PR, checks, and review package. Do not mark ready
  until Codex and Claude or equivalent deep review have checked the production
  path.
- `exclusive`: stop after each write phase. Do not start another protected-path
  PR until the current exclusive PR is closed, merged, or explicitly abandoned.

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

PR bodies should also declare `Worker-Model:` and `Reviewer-Model:` before a
non-draft governed PR is marked ready. These fields are lightweight trace
signals, not a multi-account ritual. During the warn period,
`steward/dispatch-review` reports missing, placeholder, or identical model
declarations as warnings only. If later enforced, the reviewer model must differ
from the worker model unless the steward records an explicit exception.

Use the smallest review that protects quality:

- Tier 1: docs-only, closeout-only, and low-risk hygiene PRs need CI plus Codex
  evidence. Claude review is optional.
- Tier 2: ordinary business fixes need one non-author review focused on the
  production call path.
- Tier 3: grading, auth, tenant/data isolation, runtime, migrations,
  governance gates, deletion/retirement, and silent-downgrade fixes need Codex
  review plus Claude App or `claude -p` review when budget allows.

When the user requires Claude deep review for the current program of work, treat
Claude review as mandatory for every non-trivial governed PR before leaving
draft. Claude review remains advisory evidence, not merge authority; GitHub
checks and the user's approval remain the merge gate.

For any new protection field, status, parameter, fallback, or fail-closed flag,
the review must name the production consumer. Examples: `needs_review`,
`ocr_status`, `expected_details_count`, `review_required`, `fail_closed`.
If there is no production consumer, the review must FAIL or mark the PR
incomplete.

Empty GitHub approve bodies, self-authored checklist text, and PR body claims
are not Independent Review evidence.
For non-draft governed PRs, the `steward/dispatch-review` check rejects
placeholder or non-PASS Independent Review body state. Draft PRs may keep
`Verdict: PENDING` while implementation and review are still in progress.
The gate also performs warn-only GitHub API verification for issue-comment
evidence: the comment should exist, belong to the same PR, be non-empty, and
include `Verdict: PASS`. Warnings expose weak evidence without blocking merge
until Keel explicitly moves the policy to enforcement.
