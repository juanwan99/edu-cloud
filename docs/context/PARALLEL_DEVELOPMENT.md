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
5. Use a separate worktree unless it is the only active writer.
6. Create a fresh Keel scope file with exact allowed and forbidden paths.
7. Put `Steward-Scope: <scope_id>` in the PR body.

Do not start mutating work when the mode or scope is unclear. Re-anchor with
the user instead.

## Integration Rules

- One integrator owns final merge/push for a batch.
- Central context updates happen through exclusive governed PRs.
- Workers report changed files, commit hash, verification, dirty/staged state,
  and out-of-scope residue.
- Parallel workers do not declare feature completion; completion requires
  evidence accepted by Codex/user and GitHub gates.

## Practical Default

Use this default under time pressure:

- one code writer for risky backend/core work;
- one read-only audit/review window;
- one planning/documentation window;
- optional isolated frontend-only writer when it does not touch auth/router,
  global stores, generated dist, or shared shell layout.
