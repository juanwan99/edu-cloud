---
title: edu-cloud Agent Entry
owner: liang
last_review_date: "2026-07-01"
expiration_in_days: 30
---

# edu-cloud Agent Entry

This is the active entrypoint for AI-assisted work in edu-cloud.

## Active Document Index

Before reading `docs/**`, read `docs/context/ACTIVE_INDEX.md`. It is the only
canonical index for active, candidate-active, reference, and historical docs.
Do not discover current instructions by scanning old plans or handoffs.

## Current Governance

edu-cloud uses Keel for governed changes:

1. Use one git worktree per parallel task.
2. Add one new scope file under `control/steward/scopes/` for each governed PR.
3. Change only files allowed by that scope.
4. Include `Steward-Scope: <scope_id>` in the PR body.
5. Let GitHub required checks, CODEOWNERS, and human review decide.

Each scope file is a one-time PR authorization. After its PR merges, do not
reuse it for new work. The lifecycle boundary is the fresh scope file newly
added in the PR plus an `expires_at` that remains in the future while the PR is
active. Closeout-only PRs remain supported for historical compatibility and
explicit maintenance, but they are not a routine post-merge step.

Legacy Yuanqi paths are default forbidden paths consumed by the scope gate.
Scope files do not need to hand-copy `.yuanqi/`, `scripts/yuanqi/`, or
`tests/yuanqi/` into `forbidden_paths`. Adding or modifying those paths remains
blocked, and `allowed_paths` must not name them. Deleting legacy Yuanqi files is
exempt from changed-file scope enforcement so cleanup does not look like a
revival risk.

Before launching multiple mutating workers, deleting or retiring files, or
touching `.github/**`, `control/**`, `docs/context/**`, `scripts/governance/**`,
or `tests/governance/**`, stop for Codex Dispatch Review. The review must define
task order, scope ids, allowed paths, forbidden paths, and local verification
commands before implementation starts.

Codex Dispatch Review is not, by itself, permission to write. A mutating batch
also needs an explicit user-visible write license before any worker creates a
branch, commits, pushes, opens a draft PR, edits a PR body, comments on GitHub,
or marks a PR ready. The write license must name the approved scope ids and say
whether workers may self-fix red CI. If the license is missing or ambiguous,
Codex may continue read-only scouting only and must re-anchor with the user.

Draft PRs are useful safety buffers, but they still count as writes. A worker
may open a draft PR only when the write license explicitly allows draft PR
creation for that scope. After the first push, any failing required check or
scope/body gate stops the worker by default; a fix push requires either an
explicit license that allows CI self-fix for that scope or a fresh steward/user
instruction naming the failing check.

In multi-window mode, the steward thread is not the implementation thread. The
steward thread owns intake, queue order, dispatch review, risk calls, and final
evidence readback. A task thread owns one scoped implementation PR at a time.
The same thread must not self-dispatch, implement, and then provide the
Independent Review evidence for that PR.

The PR body must include both `Steward-Scope: <scope_id>` and
`Codex-Dispatch-Review: <CDR-id-or-GitHub-comment-url>`. The CDR evidence is
issued by the non-implementing steward/reviewer before implementation starts;
workers must not invent, self-approve, or leave placeholder evidence.

GitHub enforces this through `steward/dispatch-review`: governed PRs must use a
fresh `keel/` branch based on latest `origin/master`, include non-placeholder
CDR evidence, and include a completed Dispatch Review checklist.

Dispatch Review is a pre-work boundary check. It is not the final code review.
Before merge, every non-trivial PR needs Independent Review evidence in the PR
conversation or review body. Empty approve reviews do not count as evidence.
For non-draft governed PRs, `steward/dispatch-review` requires the PR body's
Independent Review section to name the evidence URL and say `Verdict: PASS`;
`PENDING`, `REQUIRED`, or empty evidence is not merge-ready. The approving
GitHub review should include the same evidence URL in its body.

Independent Review must be done by a non-author and must state:

- files and call paths inspected;
- whether new fields, flags, parameters, or fail-closed paths have production
  consumers;
- tests or CI evidence checked;
- residual risk and a clear `PASS` or `FAIL`.

Use Claude economically: Claude App manual review is acceptable evidence when
the user runs it and pastes or links the report. `claude -p` is optional and
reserved for high-risk review, not routine closeout or docs-only PRs.
The user may paste raw Claude output; Codex is responsible for extracting and
posting the standard PR review evidence.

The old Yuanqi task-contract workflow is retired from active use. Do not create
or restore `.yuanqi/tasks`, `Yuanqi-Task:` PR markers, Yuanqi task windows, or
Yuanqi registry/scope/overlap gates.

Historical documents may still mention Yuanqi, Meta Runtime, or Guardian
Runtime. Treat those references as history unless a current Keel scope or a
current user instruction explicitly revives a specific fact.

## Roles

Keel keeps the useful dual-core responsibility split without the retired Yuanqi
task-contract machinery:

- **Meta Core** owns direction, facts, task boundaries, context,
  Claude read-only counter-review, and the completion evidence contract.
- **Guardian Core** owns dirty state, truthline, DB/migration gates,
  safety scanning, frontend/backend build-runtime consistency, and environment hygiene.

This is Codex-led and Claude-assisted: Claude may plan, review, or implement
when explicitly used, but GitHub and human review remain the merge authority.

- Codex steward thread: local steward, dispatch reviewer, final readback
  reviewer, and hygiene auditor.
- Codex implementation thread: scoped implementation helper only when the user
  explicitly assigns that role for a specific PR.
- Claude App: local planner/reviewer or implementation assistant when the user
  explicitly uses it.
- GitHub: hard gate for merge eligibility through required checks, CODEOWNERS,
  and review.

No model accepts its own work as complete. Completion requires concrete
evidence: tests, CI, runtime checks, or file-level inspection.
If Liang explicitly authorizes the steward thread to implement an exception,
state the role change before editing. That PR still needs non-author
Independent Review evidence before it is merge-ready.

## Start Here

1. Run `python scripts/codex-check` when available.
2. Inspect `git status --short --branch`.
3. Read the relevant current source files before editing.
4. For governed PRs, create a new Keel scope file before changing protected
   governance or high-risk paths.
5. Keep verification focused on the changed behavior.
6. Treat `docs/context/META_RUNTIME.md`, `docs/context/GUARDIAN_RUNTIME.md`,
   `scripts/meta-check`, and `scripts/guardian-watch` as historical/advisory
   legacy material unless a current Keel scope explicitly names them.
7. Do not open a PR until the body contains the exact `Steward-Scope: <scope_id>`
   marker, the exact `Codex-Dispatch-Review: <CDR-id-or-GitHub-comment-url>`
   marker, and the matching fresh scope file exists in the PR diff.

## Hard Bans

- Do not run `git reset --hard`, `git checkout -- .`, `git restore .`,
  `git clean -f`, or equivalent destructive cleanup unless the user explicitly
  asks.
- Do not direct-run `alembic upgrade` or `alembic downgrade` on the project DB.
  Use `scripts/db_migrate`.
- Do not copy active SQLite databases with `cp` or `rsync`; use SQLite backup
  APIs or project migration/backup tools.
- Do not edit `.env` or `.secrets` unless the user explicitly asks.
- Do not commit secrets, API keys, service-account JSON, WAL/SHM files,
  screenshots, local backups, or generated runtime artifacts.
- Do not treat old Windows-era paths, stale handoffs, or historical governance
  documents as current facts.

## Verification

Use the narrowest meaningful verification first, then rely on GitHub required
checks for merge decisions.

Common commands:

```bash
python scripts/codex-check
python scripts/codex-context --no-network
python scripts/codex-verify safety
python scripts/codex-verify safety --repo-wide
python scripts/codex-verify backend --dry-run
python scripts/codex-verify frontend --dry-run
python scripts/codex-verify schema --dry-run
```

For runtime isolation, use Docker Compose with a unique project name and ports
for each parallel task. Stop the same Compose project with `docker compose down
-v` when done.
