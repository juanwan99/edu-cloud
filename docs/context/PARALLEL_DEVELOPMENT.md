---
title: Parallel Development Policy
owner: liang
last_review_date: "2026-07-01"
expiration_in_days: 30
---

# Parallel Development Policy

Date: 2026-06-28
Purpose: let edu-cloud move faster without recreating concurrent-write
accidents.

## Baseline

- Same worktree mutating writers are forbidden.
- Parallel mutating work uses separate git worktrees.
- Governed PRs use a fresh Keel scope file under `control/steward/scopes/`.
- `read_only` and reviewer sessions may coexist with writers.
- `live_admin`, DB migration, auth, deploy, and runtime work are exclusive.
- The module dependency baseline is 0 cross-module edges and 0 cycles. Keep it
  at 0 unless a reviewed architecture decision explicitly accepts debt.

## Parallel Modes

| Mode | Allowed parallelism | Examples | Required guard |
|---|---|---|---|
| `read_only_audit` | High | Investigation, review, evidence collection | No writes, no git mutations, no DB/systemd commands |
| `planning_only` | High | Design, task planning, scope drafting | No implementation until approved |
| `docs_local` | Medium | Non-central review docs, module notes | Do not edit `AGENTS.md` or `docs/context/**` from parallel workers |
| `frontend_only` | Medium | Isolated page/component work outside auth/router/global stores | Separate worktree, exact scope, frontend verification |
| `module_writer` | Low to medium | One backend module plus its tests/docs | Separate worktree, exact module scope, dependency baseline check |
| `integration_writer` | Single | Merge, conflict resolution, cross-module wiring | One active integrator |
| `exclusive` | Single | DB migration, permissions, module gates, authGuard, runtime, deploy | No parallel mutating windows |

## Integration Lanes

Parallel implementation and merge integration are separate decisions. A task may
be safe to implement in parallel and still need guarded or exclusive integration
before it leaves draft.

| Lane | Use for | Parallel implementation | Integration rule |
|---|---|---|---|
| `independent` | Non-overlapping docs, frontend leaf work, isolated backend module changes outside shared contracts | Yes, normally up to three workers per batch | Do not rebase just to chase unrelated merges. Use scope, CI, Independent Review, and final master truthline evidence. |
| `guarded` | Silent-downgrade cleanup, grading, auth-adjacent code, shared facades, module-boundary work | Yes, when paths do not overlap and the dispatch review names dependencies | Keep draft until required checks pass and Codex plus Claude or equivalent deep review have checked the production call path. Re-sync only when the reviewer or CI evidence needs it. |
| `exclusive` | `.github/**`, rulesets, governance gates, central context, DB, runtime, deploy, auth core, permission core | No mutating parallel worker | One writer and one integration decision at a time. No unrelated PR may share the same protected contract. |

The lane is declared in the PR body and in the Dispatch Review evidence. Lanes
are not a new state file or scheduler; they are the steward's integration
decision for that PR.

GitHub Merge Queue remains the preferred mature merge-queue mechanism when the
repository owner type and GitHub plan support it and all required checks report
on `merge_group`. Until that is true, Keel must not build a replacement queue.

## Write License

Parallelism has two separate approvals:

1. **Dispatch Review** defines whether work is safe to parallelize and records
   scope ids, allowed paths, forbidden paths, dependency order, and verification
   commands.
2. **Write License** is the user-visible approval to perform writes for those
   scopes.

Without a write license, Codex and subagents may only do `read_only_audit` or
`planning_only` work. The following all count as writes: creating a branch,
committing, pushing, opening a draft PR, editing a PR body, posting a GitHub
comment, requesting review, marking a PR ready, closing a PR, or modifying issue
metadata. "Draft" reduces merge risk, but it is not a substitute for write
permission.

A write license must name:

- approved scope ids or PR titles;
- the integration lane for each scope;
- whether draft PR creation is allowed;
- whether the worker may self-fix red CI after the first push;
- the stop condition that returns control to the steward/user.

Default stop condition: workers stop after opening the first draft PR. If any
required check, PR-body gate, or scope gate fails, the worker reports the
failure and waits. They do not push a fix unless the write license explicitly
allowed CI self-fix for that scope or the steward/user issues a new targeted
instruction.

## Exclusive Scopes

Only one mutating window may touch these areas at a time:

- DB migrations, SQLite files, `scripts/db_migrate`, `scripts/db_doctor.py`.
- Runtime and deployment: systemd, backend/worker restart, nginx, dist publish.
- Permission and module-gating core: auth, tenant, permissions, authGuard,
  module middleware, `module-semantics.yaml`, and route guards.
- Central context and entrypoints: `AGENTS.md`, `CLAUDE.md`,
  `docs/context/**`.
- Governance infrastructure: `.github/**`, `control/**`, `conftest/**`,
  `.semgrep/**`, Gitleaks config, CODEOWNERS, and governance tests/scripts.
- Module dependency baseline files and portal/shared foundation modules.

## Launch Rules

Before launching another mutating window:

1. Run `scripts/codex-check` when available.
2. Inspect `git status --short --branch`.
3. Run `python scripts/governance/check_module_dependencies.py --check` for
   backend module work.
4. Classify the task into one mode above.
5. Classify the integration lane as `independent`, `guarded`, or `exclusive`.
6. Use a separate worktree unless it is the only active writer.
7. Create a fresh Keel scope file with exact allowed paths and any
   task-specific forbidden paths.
8. Put `Steward-Scope: <scope_id>` in the PR body.
9. Put `Codex-Dispatch-Review: <CDR-id-or-GitHub-comment-url>` in the PR body.
10. Complete the Dispatch Review checklist before implementation begins.
11. Obtain the write license before creating branches, commits, pushes, draft
    PRs, comments, PR-body edits, or ready-for-review transitions.

The CDR value must come from the non-implementing steward/reviewer before
implementation starts. Workers must not self-issue or guess it.

Fresh scope files are one-time PR authorizations; do not reuse them after merge.
Their active lifecycle boundary is the newly added scope file plus a future
`expires_at`. Closeout-only PRs remain a compatibility path, not the normal
parallel-work lifecycle. Legacy Yuanqi paths are default forbidden by the gate,
so workers should not copy `.yuanqi/`, `scripts/yuanqi/`, or `tests/yuanqi/`
into every scope file.

Do not start mutating work when the mode or scope is unclear. Re-anchor with
the user instead.

Codex Dispatch Review is mandatory before launching:

- two or more mutating workers;
- deletion or retirement work;
- `.github/**`, `control/**`, `docs/context/**`, `scripts/governance/**`, or
  `tests/governance/**` changes;
- runtime, deploy, auth, permission, DB, or module-boundary changes.

The review decides whether work may run in parallel. If tasks share files,
depend on each other, or change the same governance contract, use one integrator
or strictly ordered PRs instead of parallel worker PRs.

## Integration Rules

- One integrator owns final merge/push for a batch.
- The steward may keep several `independent` PRs open at once when their changed
  files and production call paths do not overlap.
- `Guarded` PRs may be implemented in parallel, but they leave draft only after
  required checks and the required deep review evidence are present.
- `Exclusive` PRs reserve their protected contract until the PR is closed or
  merged. Do not start another mutating PR against that contract.
- Central context updates happen through exclusive governed PRs.
- Workers report changed files, commit hash, verification, dirty/staged state,
  and out-of-scope residue.
- Parallel workers do not declare feature completion; completion requires
  evidence accepted by Codex/user and GitHub gates.
- Draft PR creation is not completion and is not merge readiness. Draft PRs are
  queue items that wait for checks, Independent Review, Claude review when
  required, and user approval.
- Workers do not self-repair failing checks after their first push unless the
  batch write license explicitly says that CI self-fix is allowed for that
  scope. Otherwise the steward triages and asks for targeted authorization.
- Deletion workers must report reachability evidence across scripts, tests,
  workflows, active docs, and governance registries before removing files.
- Independent reviewers do not push to the implementation branch. If the
  reviewer must fix or rebase, they become a contributor and a fresh
  non-author review is required.
- Empty approve reviews do not count as Independent Review. The review evidence
  must state checked files, checked call paths, production consumers for any new
  protection fields or parameters, verification evidence, and PASS/FAIL.
- Before a governed PR leaves draft, the PR body must point to that evidence and
  say `Verdict: PASS`; the approving GitHub review should include the same
  evidence URL instead of an empty body.
- A stale branch is not automatically a bug for an `independent` PR. It becomes
  a blocker only when GitHub required checks, the reviewer, or the declared
  integration lane requires a fresh base.

## Practical Default

Use this default under time pressure:

- one code writer for risky backend/core work;
- one read-only audit/review window;
- one planning/documentation window;
- optional isolated frontend-only writer when it does not touch auth/router,
  global stores, generated dist, or shared shell layout.

Use this default for speed without drift:

- one batch proposal listing all candidate scopes and write-license terms;
- at most three non-overlapping mutating workers per batch;
- declare one integration lane per worker before writes begin;
- red CI stops workers unless the batch explicitly allows self-fix;
- central context, governance infrastructure, auth/permission/runtime/DB, and
  cross-module integration remain single-writer;
- Claude deep review is scheduled after checks pass and before a governed PR
  leaves draft when the task is high risk or the user requires it.
