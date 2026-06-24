# Parallel Development Policy

Date: 2026-06-11
Purpose: let edu-cloud move faster without recreating concurrent-write
accidents.

## Current Baseline

- Yuanqi governance allows multiple windows at the operator layer only when project,
  worktree, and scope make the collision risk explicit.
- Same worktree mutating writers are forbidden.
- Different worktrees with overlapping scope are warned, not assumed safe.
- `read_only` and reviewer sessions may coexist with writers.
- `live_admin` is global-exclusive and blocks other mutating sessions.
- Contract-bound writes still pass through the Yuanqi scope gate. Treat
  code-write parallelism as controlled and serialized at risky boundaries, not
  free-form simultaneous editing.
- edu-cloud module dependency baseline is currently 55 cross-module edges and
  30 historical cycles. That is accepted debt, not a reason to add more.

## Parallel Modes

| Mode | Allowed parallelism | Examples | Required guard |
|---|---|---|---|
| `read_only_audit` | High | Investigation, review, evidence collection, test-gap analysis | No writes, no git mutations, no DB/systemd commands |
| `planning_only` | High | Yuance planning, contract drafting, task packet preparation | No Claude execution until approved |
| `docs_local` | Medium | Non-central review docs, task reports, module notes | Do not edit `AGENTS.md` or `docs/context/**` from parallel workers |
| `frontend_only` | Medium | Isolated page/component work outside auth/router/global stores | Separate worktree, exact scope, frontend verification |
| `module_writer` | Low to medium | One backend module plus its tests/docs | Separate worktree, exact module scope, dependency baseline check |
| `integration_writer` | Single | Merge, conflict resolution, cross-module wiring, release notes | One active integrator |
| `exclusive` | Single | DB migration, permissions, module gates, authGuard, runtime, deploy | No parallel mutating windows |

## Exclusive Scopes

Only one mutating window may touch these areas at a time:

- DB migrations, SQLite files, `scripts/db_migrate`, `scripts/db_doctor.py`.
- Runtime and deployment: systemd, backend/worker restart, nginx, dist publish.
- Permission and module-gating core: `permissions.py`, frontend permission
  mirror, `module-semantics.yaml`, authGuard, route guards, module middleware.
- Central context and entrypoint files: `AGENTS.md`, `docs/context/**`.
- Module dependency baseline updates: `docs/governance/module-dependencies.yaml`
  and `scripts/governance/check_module_dependencies.py`.
- Portal aggregation contracts and cross-module service registry work.
- Shared foundation modules such as `student`, `profile`, `school`, and
  school-module settings when the change affects more than one consumer.

## Launch Rules

Before launching another execution window:

1. Run `scripts/codex-check`.
2. Run `scripts/meta-check --task "<task>" --write-state`.
3. Run `python3 scripts/governance/check_module_dependencies.py --check` for
   backend module work.
4. Check current dirty files with `git status --short --branch`.
5. Classify the task into one mode above.
6. If mutating, use a separate worktree unless it is the only active writer.
7. Declare the exact allowed and forbidden scope in the Yuanqi task contract.
8. Record the Claude window as `sid:<short-id>` in user-facing notes.

Do not start a mutating Claude window when the mode is unclear. Return to Codex
with the classification question instead.

## Contract Requirements

Every mutating Claude packet must include:

- mode classification from this file;
- allowed write scope;
- forbidden scope;
- exact verification commands;
- stop conditions for scope expansion, test contradiction, new coupling, dirty
  residue, DB/runtime need, or unexpected files;
- git rules: whether commit is allowed, whether push is forbidden, and who
  owns integration.

Default git rule: worker windows may commit only when the task contract
explicitly allows it. Push is owned by the integrator or Codex unless the
contract explicitly grants push authority.

## Integration Rules

- One integrator owns final merge/push for a batch.
- Central context files (`AGENTS.md`, `docs/context/**`) are updated through a
  dedicated exclusive governed window (active Yuanqi task contract) after Codex
  accepts the worker results; Codex does not edit them directly (Q1 ruling,
  `docs/reviews/2026-06-12-w1-governance-acceptance.md`).
- A worker closeout must report `sid`, contract id/hash, changed files, commit
  hash if any, verification commands, dirty/staged status, and out-of-scope
  residue.
- Parallel workers do not declare feature completion. Codex accepts or rejects
  the evidence and then updates current facts.

## Practical Default Under Time Pressure

Use this default until the dependency baseline is reduced:

- one code writer for risky backend/core work;
- one read-only audit/review window;
- one planning/documentation window;
- optional isolated frontend-only writer when it does not touch auth/router,
  global stores, generated dist, or shared shell layout.

This gives useful speedup now while preserving the path toward deeper module
decoupling.
